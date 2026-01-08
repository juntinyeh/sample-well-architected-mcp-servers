# Nested CloudFormation Templates for Cloud Optimization Assistant

This directory contains modular, nested CloudFormation templates for deploying the Cloud Optimization Assistant (COA) platform.

## Architecture Overview

The deployment uses a master/nested stack architecture to provide:
- **Modularity**: Each component can be updated independently
- **Reusability**: Templates can be reused across environments
- **Maintainability**: Easier to understand and modify individual components
- **Best Practices**: Follows AWS CloudFormation best practices

## Template Structure

```
cloudformation-nested/
├── master.yaml          # Master template orchestrating all nested stacks
├── auth.yaml           # Cognito authentication stack
├── storage.yaml        # S3 buckets and private ECR repository
├── network.yaml        # VPC, subnets, security groups
├── cicd.yaml           # CodePipeline and CodeBuild
└── compute.yaml        # ECS cluster, ALB, and services
```

## Component Details

### 1. Master Template (`master.yaml`)

The master template orchestrates all nested stacks with proper dependencies.

**Key Features:**
- Parameter validation and defaults
- Cross-stack references
- Comprehensive outputs
- Dependency management

**Parameters:**
- Environment (dev/staging/prod)
- ParameterPrefix (SSM parameter prefix)
- Source and templates bucket names
- Network CIDR blocks
- Container resources

### 2. Authentication Stack (`auth.yaml`)

Manages Cognito User Pools and Identity Pools.

**Resources Created:**
- Cognito User Pool with MFA support
- User Pool Domain
- Web and API clients
- Identity Pool
- IAM roles for authenticated users
- SSM parameters for configuration

**Outputs:**
- User Pool ID and ARN
- Client IDs
- Identity Pool ID

### 3. Storage Stack (`storage.yaml`)

Manages S3 buckets and private ECR repository.

**Resources Created:**
- **Artifacts Bucket**: For CodePipeline artifacts with versioning and lifecycle
- **Logs Bucket**: For CloudFront and ALB logs
- **Frontend Bucket**: For static website hosting
- **Private ECR Repository**: For container images with:
  - Image scanning on push
  - Lifecycle policies (keep last 10 images)
  - Encryption at rest
  - Repository policies for ECS and CodeBuild access

**Key Features:**
- Encryption at rest (AES256)
- Lifecycle policies for cost optimization
- Public access blocks
- CORS configuration for frontend
- ECR policies for least-privilege access

**Outputs:**
- Bucket names and ARNs
- ECR repository URI
- Frontend website URL

### 4. Network Stack (`network.yaml`)

Creates VPC with public and private subnets across two availability zones.

**Resources Created:**
- VPC with DNS support
- Internet Gateway
- 2 Public Subnets (for ALB)
- 2 Private Subnets (for ECS tasks)
- 2 NAT Gateways (one per AZ for high availability)
- Route Tables with proper routes
- Security Groups:
  - ALB Security Group (HTTP/HTTPS from internet)
  - ECS Security Group (port 8000 from ALB)
  - CodeBuild Security Group (outbound only)
- VPC Endpoints:
  - S3 (Gateway endpoint)
  - ECR API (Interface endpoint)
  - ECR DKR (Interface endpoint)
  - CloudWatch Logs (Interface endpoint)

**Design Principles:**
- High availability (multi-AZ)
- Secure by default (private subnets for workloads)
- Cost-optimized (VPC endpoints reduce NAT costs)

**Outputs:**
- VPC ID
- Subnet IDs
- Security Group IDs

### 5. CI/CD Stack (`cicd.yaml`)

Implements continuous integration and deployment pipeline.

**Resources Created:**
- **CodeBuild Project**: Builds Docker images from source
- **CodePipeline**: Automated deployment pipeline with 3 stages:
  1. **Source**: S3 source bucket
  2. **Build**: CodeBuild builds and pushes to private ECR
  3. **Deploy**: ECS rolling deployment
- **EventBridge Rule**: Triggers pipeline on source changes
- **IAM Roles**: Least-privilege roles for CodeBuild and CodePipeline

**Build Process:**
```
Source Code (S3) → CodeBuild → Docker Build → Push to Private ECR → ECS Deploy
```

**BuildSpec Highlights:**
- Logs into private ECR
- Builds Docker image with commit hash tag
- Pushes both commit-hash and latest tags
- Generates imagedefinitions.json for ECS
- Runs in VPC for secure access

**Outputs:**
- Pipeline name and ARN
- CodeBuild project name and ARN

### 6. Compute Stack (`compute.yaml`)

Manages ECS cluster, Application Load Balancer, and services.

**Resources Created:**
- **ECS Cluster** with Container Insights
- **Application Load Balancer**:
  - Internet-facing
  - HTTP listener (port 80)
  - Health checks to /health endpoint
- **Target Group** with sticky sessions
- **ECS Task Definition**:
  - Fargate launch type
  - Uses images from private ECR
  - Environment variables for AgentCore configuration
  - CloudWatch Logs integration
  - Health check command
- **ECS Service**:
  - Rolling deployments
  - Circuit breaker with automatic rollback
  - Multiple availability zones
- **Auto Scaling**:
  - Target tracking based on CPU (70%)
  - Target tracking based on Memory (80%)
  - Scale 1-10 tasks

**IAM Roles:**
- **Task Execution Role**: ECR pull, SSM parameter access
- **Task Role**: Bedrock AgentCore, SSM, CloudWatch Logs

**Outputs:**
- Cluster name and ARN
- Service name and ARN
- Load Balancer DNS and URL
- Target Group ARN

## Deployment Guide

### Prerequisites

1. **S3 Buckets**: Create two S3 buckets:
   ```bash
   # Source code bucket
   aws s3 mb s3://my-coa-source-bucket
   
   # Templates bucket
   aws s3 mb s3://my-coa-templates-bucket
   ```

2. **Upload Templates**: Upload nested templates to templates bucket:
   ```bash
   aws s3 sync cloudformation-nested/ s3://my-coa-templates-bucket/ \
     --exclude "master.yaml" \
     --exclude "README.md"
   ```

3. **Upload Source Code**: Package and upload source code:
   ```bash
   cd cloud-optimization-web-interfaces/cloud-optimization-web-interface
   zip -r ../../source.zip .
   cd ../..
   aws s3 cp source.zip s3://my-coa-source-bucket/
   ```

### Deploy Stack

**Option 1: Using AWS CLI**

```bash
aws cloudformation create-stack \
  --stack-name coa-prod \
  --template-body file://cloudformation-nested/master.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=prod \
    ParameterKey=SourceBucketName,ParameterValue=my-coa-source-bucket \
    ParameterKey=TemplatesBucketName,ParameterValue=my-coa-templates-bucket \
    ParameterKey=SourceCodeKey,ParameterValue=source.zip \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

**Option 2: Using deploy-coa.sh**

```bash
./deploy-coa.sh --stack-name coa-prod --region us-east-1 --agentcore-only
```

### Monitor Deployment

```bash
# Watch stack creation progress
aws cloudformation describe-stacks \
  --stack-name coa-prod \
  --query 'Stacks[0].StackStatus'

# View stack events
aws cloudformation describe-stack-events \
  --stack-name coa-prod \
  --max-items 10
```

### Update Stack

To update individual components, modify the nested template and sync to S3:

```bash
# Update storage stack
aws s3 cp cloudformation-nested/storage.yaml s3://my-coa-templates-bucket/

# Update master stack (triggers nested stack update)
aws cloudformation update-stack \
  --stack-name coa-prod \
  --template-body file://cloudformation-nested/master.yaml \
  --parameters ParameterKey=Environment,UsePreviousValue=true \
  --capabilities CAPABILITY_IAM
```

## Stack Dependencies

The stacks have the following dependency order:

```
1. AuthStack (independent)
2. StorageStack (independent)
3. NetworkStack (independent)
4. CiCdStack (depends on: StorageStack, NetworkStack)
5. ComputeStack (depends on: NetworkStack, StorageStack, AuthStack, CiCdStack)
```

## Resource Tagging

All resources are tagged with:
- **Environment**: dev/staging/prod
- **Component**: Resource type (Cognito, Storage, Network, etc.)
- Additional component-specific tags

## Cost Optimization

The templates include several cost optimization features:

1. **S3 Lifecycle Policies**: Automatically delete old artifacts and transition to cheaper storage
2. **ECR Lifecycle Policies**: Keep only last 10 images, delete untagged after 7 days
3. **VPC Endpoints**: Reduce NAT Gateway data transfer costs
4. **Auto Scaling**: Scale down to minimum during low usage
5. **Fargate Spot** (optional): Can be enabled for non-production environments

## Security Features

1. **Least Privilege IAM**: Each role has minimal required permissions
2. **Private Subnets**: Workloads run in private subnets
3. **Security Groups**: Restrictive ingress/egress rules
4. **Encryption**: At-rest and in-transit encryption
5. **VPC Endpoints**: Private AWS service access
6. **ECR Image Scanning**: Automatic vulnerability scanning
7. **Private ECR**: Container images in private registry (not public ECR)

## Troubleshooting

### Common Issues

**1. Nested Stack Creation Failed**

Check nested stack events:
```bash
aws cloudformation describe-stack-events \
  --stack-name coa-prod-NetworkStack-XXXXX
```

**2. ECR Push Fails**

Verify CodeBuild has ECR permissions:
```bash
aws iam get-role-policy \
  --role-name coa-prod-CodeBuildServiceRole-XXXXX \
  --policy-name CodeBuildPolicy
```

**3. ECS Service Won't Start**

Check ECS task logs:
```bash
aws logs tail /ecs/coa-prod/backend --follow
```

**4. Image Pull from Private ECR Fails**

Verify:
- ECR repository policy allows ECS
- Task execution role has ECR permissions
- VPC endpoints for ECR are configured

### Validation Commands

```bash
# Validate master template
aws cloudformation validate-template \
  --template-body file://cloudformation-nested/master.yaml

# Validate nested template
aws cloudformation validate-template \
  --template-body file://cloudformation-nested/compute.yaml

# Check stack drift
aws cloudformation detect-stack-drift \
  --stack-name coa-prod
```

## CI/CD Pipeline Details

### Pipeline Stages

1. **Source Stage**
   - Triggered by S3 source changes via EventBridge
   - Pulls source.zip from source bucket
   - Outputs: SourceOutput artifact

2. **Build Stage**
   - Runs CodeBuild project
   - Logs into private ECR
   - Builds Docker image
   - Pushes to private ECR with tags
   - Outputs: BuildOutput (imagedefinitions.json)

3. **Deploy Stage**
   - ECS rolling update
   - Uses imagedefinitions.json
   - Updates service with new image from private ECR
   - Circuit breaker with automatic rollback

### Buildspec Details

The CodeBuild project uses an inline buildspec that:
- Uses AWS CodeBuild standard:7.0 image
- Runs in VPC for security
- Has privileged mode for Docker
- Environment variables:
  - AWS_DEFAULT_REGION
  - AWS_ACCOUNT_ID
  - IMAGE_REPO_NAME
  - ECR_REPOSITORY_URI

### Deployment Strategy

- **Type**: Rolling update
- **MaximumPercent**: 200% (allows 2x tasks during deployment)
- **MinimumHealthyPercent**: 100% (ensures no downtime)
- **Circuit Breaker**: Enabled with automatic rollback
- **Health Check**: /health endpoint every 30s

## Outputs Reference

After deployment, retrieve outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name coa-prod \
  --query 'Stacks[0].Outputs'
```

Key outputs:
- **LoadBalancerUrl**: Application URL
- **EcrRepositoryUri**: Private ECR repository for images
- **UserPoolId**: Cognito User Pool
- **ECSClusterName**: ECS cluster name
- **CodePipelineName**: Pipeline name

## Best Practices

1. **Use Parameter Store**: Store configuration in SSM Parameter Store with prefix
2. **Version Control**: Keep templates in Git
3. **Testing**: Test in dev environment before production
4. **Monitoring**: Enable CloudWatch Container Insights
5. **Backups**: Enable versioning on S3 buckets
6. **Updates**: Use change sets for production updates
7. **Private ECR**: Always use private ECR for production images

## Support and Maintenance

- Templates follow CloudFormation best practices
- All resources use latest AWS service features
- Regular updates for security patches
- Compatible with AWS CLI v2 and CloudFormation v1

## License

MIT No Attribution - see LICENSE file for details.
