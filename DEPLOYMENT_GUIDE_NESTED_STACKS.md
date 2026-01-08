# Deployment Guide: Nested CloudFormation Stacks

This guide explains how to deploy the Cloud Optimization Assistant (COA) using the new modular, nested CloudFormation architecture.

## Overview

The new deployment architecture uses nested CloudFormation stacks for:
- **Modularity**: Update individual components independently
- **Maintainability**: Easier to understand and modify
- **Reusability**: Share templates across environments
- **Best Practices**: Follows AWS CloudFormation recommendations
- **Private ECR**: Uses private ECR repository instead of public ECR from another account

## Architecture Components

The deployment consists of 6 modular stacks:

1. **Auth Stack**: Cognito authentication and authorization
2. **Storage Stack**: S3 buckets and private ECR repository
3. **Network Stack**: VPC, subnets, security groups, and VPC endpoints
4. **CI/CD Stack**: CodePipeline and CodeBuild for automated deployments
5. **Compute Stack**: ECS cluster, ALB, and Fargate services
6. **Master Stack**: Orchestrates all nested stacks

## Prerequisites

### 1. AWS Account Setup
- AWS CLI installed and configured
- Appropriate IAM permissions for CloudFormation, S3, ECR, ECS, etc.
- AWS account with sufficient service quotas

### 2. Create S3 Buckets

Create two S3 buckets:

```bash
# Source code bucket
SOURCE_BUCKET="my-coa-source-$(date +%s)"
aws s3 mb s3://$SOURCE_BUCKET --region us-east-1

# CloudFormation templates bucket
TEMPLATES_BUCKET="my-coa-templates-$(date +%s)"
aws s3 mb s3://$TEMPLATES_BUCKET --region us-east-1

echo "Source Bucket: $SOURCE_BUCKET"
echo "Templates Bucket: $TEMPLATES_BUCKET"
```

Save these bucket names for later use.

### 3. Prepare Source Code

Package the source code:

```bash
cd cloud-optimization-web-interfaces/cloud-optimization-web-interface
zip -r ../../source.zip . \
    -x "*.git*" \
    -x "*node_modules*" \
    -x "*__pycache__*" \
    -x "*.DS_Store"
cd ../..

# Upload to source bucket
aws s3 cp source.zip s3://$SOURCE_BUCKET/
```

## Deployment Methods

### Method 1: Quick Deploy Script (Recommended)

Use the provided deployment script:

```bash
cd deployment-scripts

./deploy-nested-stacks.sh \
    --stack-name coa-prod \
    --region us-east-1 \
    --environment prod \
    --source-bucket $SOURCE_BUCKET \
    --templates-bucket $TEMPLATES_BUCKET
```

**Options**:
- `--stack-name`: CloudFormation stack name (default: coa-prod)
- `--region`: AWS region (default: us-east-1)
- `--environment`: Environment type: dev/staging/prod (default: prod)
- `--source-bucket`: S3 bucket with source code (required)
- `--templates-bucket`: S3 bucket for nested templates (required)

The script will:
1. Upload nested templates to S3
2. Validate templates
3. Create/update CloudFormation stack
4. Wait for completion
5. Display stack outputs

### Method 2: Manual Deployment

#### Step 1: Upload Nested Templates

```bash
cd deployment-scripts
aws s3 sync cloudformation-nested/ s3://$TEMPLATES_BUCKET/ \
    --exclude "master.yaml" \
    --exclude "README.md" \
    --region us-east-1
```

#### Step 2: Validate Master Template

```bash
aws cloudformation validate-template \
    --template-body file://cloudformation-nested/master.yaml \
    --region us-east-1
```

#### Step 3: Create Stack

```bash
aws cloudformation create-stack \
    --stack-name coa-prod \
    --template-body file://cloudformation-nested/master.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=prod \
        ParameterKey=ParameterPrefix,ParameterValue=coa \
        ParameterKey=SourceBucketName,ParameterValue=$SOURCE_BUCKET \
        ParameterKey=TemplatesBucketName,ParameterValue=$TEMPLATES_BUCKET \
        ParameterKey=SourceCodeKey,ParameterValue=source.zip \
    --capabilities CAPABILITY_IAM \
    --region us-east-1
```

#### Step 4: Monitor Deployment

```bash
# Watch stack status
aws cloudformation describe-stacks \
    --stack-name coa-prod \
    --query 'Stacks[0].StackStatus' \
    --output text

# Wait for completion
aws cloudformation wait stack-create-complete \
    --stack-name coa-prod \
    --region us-east-1
```

#### Step 5: View Outputs

```bash
aws cloudformation describe-stacks \
    --stack-name coa-prod \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table
```

## Post-Deployment

### 1. Verify Deployment

Check that all nested stacks were created successfully:

```bash
aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --query 'StackSummaries[?contains(StackName, `coa-prod`)].{Name:StackName,Status:StackStatus}' \
    --output table
```

You should see 6 stacks:
- coa-prod (master)
- coa-prod-AuthStack-*
- coa-prod-StorageStack-*
- coa-prod-NetworkStack-*
- coa-prod-CiCdStack-*
- coa-prod-ComputeStack-*

### 2. Get Load Balancer URL

```bash
ALB_URL=$(aws cloudformation describe-stacks \
    --stack-name coa-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerUrl`].OutputValue' \
    --output text)

echo "Application URL: $ALB_URL"
```

### 3. Trigger CI/CD Pipeline

The pipeline will automatically trigger when you upload source code:

```bash
aws s3 cp source.zip s3://$SOURCE_BUCKET/
```

Monitor pipeline execution:

```bash
PIPELINE_NAME=$(aws cloudformation describe-stacks \
    --stack-name coa-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`CodePipelineName`].OutputValue' \
    --output text)

aws codepipeline get-pipeline-state \
    --name $PIPELINE_NAME \
    --query 'stageStates[*].{Stage:stageName,Status:latestExecution.status}' \
    --output table
```

### 4. Access Application

Once the pipeline completes:

```bash
# Test health endpoint
curl $ALB_URL/health | jq .

# View in browser
echo "Open in browser: $ALB_URL"
```

### 5. Configure Frontend

Update the frontend configuration with the backend URL:

```bash
# Get the ALB URL
echo "Backend URL: $ALB_URL"

# Update frontend/config.js with this URL
```

## Monitoring and Troubleshooting

### View Logs

```bash
# ECS task logs
aws logs tail /ecs/coa-prod/backend --follow

# CodeBuild logs
aws logs tail /aws/codebuild/coa-prod-backend-build --follow
```

### Check ECS Service

```bash
CLUSTER_NAME=$(aws cloudformation describe-stacks \
    --stack-name coa-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`ECSClusterName`].OutputValue' \
    --output text)

SERVICE_NAME=$(aws cloudformation describe-stacks \
    --stack-name coa-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`ECSServiceName`].OutputValue' \
    --output text)

aws ecs describe-services \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}' \
    --output table
```

### View ECR Repository

```bash
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name coa-prod \
    --query 'Stacks[0].Outputs[?OutputKey==`EcrRepositoryUri`].OutputValue' \
    --output text)

echo "ECR Repository: $ECR_URI"

# List images
REPO_NAME=$(echo $ECR_URI | cut -d'/' -f2)
aws ecr describe-images --repository-name $REPO_NAME
```

### Common Issues

#### 1. Stack Creation Failed

```bash
# View failed events
aws cloudformation describe-stack-events \
    --stack-name coa-prod \
    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' \
    --output table
```

#### 2. ECS Tasks Not Starting

Check task failures:

```bash
aws ecs list-tasks \
    --cluster $CLUSTER_NAME \
    --desired-status STOPPED \
    --query 'taskArns[0]' \
    --output text | xargs -I {} aws ecs describe-tasks \
    --cluster $CLUSTER_NAME \
    --tasks {} \
    --query 'tasks[0].stoppedReason'
```

#### 3. Pipeline Failures

```bash
# Get failed pipeline execution
aws codepipeline get-pipeline-execution \
    --pipeline-name $PIPELINE_NAME \
    --pipeline-execution-id <execution-id>
```

## Updating the Stack

### Update Individual Component

To update a specific component (e.g., compute stack):

```bash
# 1. Modify the nested template
# Edit cloudformation-nested/compute.yaml

# 2. Upload updated template
aws s3 cp cloudformation-nested/compute.yaml s3://$TEMPLATES_BUCKET/

# 3. Update master stack (triggers nested stack update)
aws cloudformation update-stack \
    --stack-name coa-prod \
    --template-body file://cloudformation-nested/master.yaml \
    --parameters \
        ParameterKey=Environment,UsePreviousValue=true \
        ParameterKey=SourceBucketName,UsePreviousValue=true \
        ParameterKey=TemplatesBucketName,UsePreviousValue=true \
    --capabilities CAPABILITY_IAM
```

### Update Source Code Only

To deploy new code without changing infrastructure:

```bash
# 1. Package new source code
cd cloud-optimization-web-interfaces/cloud-optimization-web-interface
zip -r ../../source.zip .
cd ../..

# 2. Upload to S3 (triggers pipeline automatically)
aws s3 cp source.zip s3://$SOURCE_BUCKET/
```

### Rolling Back

If deployment fails:

```bash
# Cancel update in progress
aws cloudformation cancel-update-stack --stack-name coa-prod

# Or delete and recreate
aws cloudformation delete-stack --stack-name coa-prod
# Then redeploy
```

## Cost Optimization

### Development Environment

For development, reduce costs:

```bash
aws cloudformation create-stack \
    --stack-name coa-dev \
    --template-body file://cloudformation-nested/master.yaml \
    --parameters \
        ParameterKey=Environment,ParameterValue=dev \
        ParameterKey=ContainerCpu,ParameterValue=256 \
        ParameterKey=ContainerMemory,ParameterValue=512 \
        ParameterKey=DesiredCount,ParameterValue=1 \
    --capabilities CAPABILITY_IAM
```

### Cleanup

To delete all resources:

```bash
# Delete stack (deletes all nested stacks)
aws cloudformation delete-stack --stack-name coa-prod

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name coa-prod

# Clean up S3 buckets (must be done manually)
aws s3 rm s3://$SOURCE_BUCKET --recursive
aws s3 rb s3://$SOURCE_BUCKET

aws s3 rm s3://$TEMPLATES_BUCKET --recursive
aws s3 rb s3://$TEMPLATES_BUCKET

# Clean up ECR images
aws ecr batch-delete-image \
    --repository-name coa-prod-backend \
    --image-ids imageTag=latest
```

## Security Best Practices

1. **Use Private ECR**: Always use private ECR repository (configured by default)
2. **Enable MFA**: Enable MFA for Cognito users
3. **HTTPS Only**: Add ACM certificate and configure HTTPS listener
4. **WAF**: Consider adding AWS WAF for additional protection
5. **VPC Endpoints**: Already configured for S3, ECR, CloudWatch
6. **Least Privilege**: IAM roles follow least privilege principle
7. **Encryption**: S3 and ECR encryption enabled by default

## Testing

Run end-to-end integration tests:

```bash
cd cloud-optimization-web-interfaces/cloud-optimization-web-interface/backend

# Install dependencies
pip3 install -r requirements.txt

# Run tests
python3 tests/e2e_integration_test.py \
    --backend-url $ALB_URL \
    --test-streaming \
    --test-long-running \
    --verbose
```

## Support

For issues:
1. Check CloudFormation events: `aws cloudformation describe-stack-events`
2. Review CloudWatch Logs: `aws logs tail /ecs/coa-prod/backend`
3. Check ECS task status: `aws ecs describe-services`
4. Validate IAM roles: `aws iam get-role-policy`
5. See detailed README: `deployment-scripts/cloudformation-nested/README.md`

## Additional Resources

- **CloudFormation Templates**: `deployment-scripts/cloudformation-nested/`
- **Implementation Summary**: `IMPLEMENTATION_SUMMARY.md`
- **Deploy Script**: `deployment-scripts/deploy-nested-stacks.sh`
- **E2E Tests**: `backend/tests/e2e_integration_test.py`

---

**Last Updated**: 2025
**Version**: 1.0.0
