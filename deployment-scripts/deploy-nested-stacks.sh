#!/bin/bash
# Quick Deployment Script for Nested CloudFormation Templates
# This script helps deploy the COA platform using nested CloudFormation templates

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
STACK_NAME="coa-prod"
REGION="us-east-1"
ENVIRONMENT="prod"
SOURCE_BUCKET=""
TEMPLATES_BUCKET=""

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Cloud Optimization Assistant using nested CloudFormation templates.

OPTIONS:
    -s, --stack-name NAME       Stack name (default: coa-prod)
    -r, --region REGION         AWS region (default: us-east-1)
    -e, --environment ENV       Environment: dev/staging/prod (default: prod)
    --source-bucket BUCKET      S3 bucket containing source code
    --templates-bucket BUCKET   S3 bucket containing nested templates
    -h, --help                  Show this help message

EXAMPLES:
    # Deploy with default settings
    $0 --source-bucket my-source --templates-bucket my-templates

    # Deploy to specific region
    $0 --region us-west-2 --source-bucket my-source --templates-bucket my-templates

    # Deploy dev environment
    $0 --environment dev --source-bucket my-source --templates-bucket my-templates

PREREQUISITES:
    1. Create S3 buckets for source and templates
    2. Upload source code to source bucket
    3. Upload nested templates to templates bucket
    4. Configure AWS CLI with appropriate credentials

EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --source-bucket)
            SOURCE_BUCKET="$2"
            shift 2
            ;;
        --templates-bucket)
            TEMPLATES_BUCKET="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required parameters
if [ -z "$SOURCE_BUCKET" ] || [ -z "$TEMPLATES_BUCKET" ]; then
    print_error "Source bucket and templates bucket are required!"
    usage
fi

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Environment must be one of: dev, staging, prod"
    exit 1
fi

print_info "Starting COA deployment with nested CloudFormation templates..."
print_info "Stack Name: $STACK_NAME"
print_info "Region: $REGION"
print_info "Environment: $ENVIRONMENT"
print_info "Source Bucket: $SOURCE_BUCKET"
print_info "Templates Bucket: $TEMPLATES_BUCKET"
echo ""

# Step 1: Upload nested templates to S3
print_info "Step 1: Uploading nested templates to S3..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/cloudformation-nested"

if [ ! -d "$TEMPLATES_DIR" ]; then
    print_error "Templates directory not found: $TEMPLATES_DIR"
    exit 1
fi

aws s3 sync "$TEMPLATES_DIR" "s3://$TEMPLATES_BUCKET/" \
    --exclude "master.yaml" \
    --exclude "README.md" \
    --exclude ".DS_Store" \
    --region "$REGION"

print_info "✓ Nested templates uploaded successfully"
echo ""

# Step 2: Validate master template
print_info "Step 2: Validating master template..."
aws cloudformation validate-template \
    --template-body "file://$TEMPLATES_DIR/master.yaml" \
    --region "$REGION" > /dev/null

print_info "✓ Template validation passed"
echo ""

# Step 3: Create or update stack
print_info "Step 3: Deploying CloudFormation stack..."

STACK_EXISTS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].StackName' \
    --output text 2>/dev/null || echo "")

if [ -n "$STACK_EXISTS" ]; then
    print_warning "Stack exists, updating..."
    OPERATION="update-stack"
else
    print_info "Creating new stack..."
    OPERATION="create-stack"
fi

aws cloudformation "$OPERATION" \
    --stack-name "$STACK_NAME" \
    --template-body "file://$TEMPLATES_DIR/master.yaml" \
    --parameters \
        ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
        ParameterKey=ParameterPrefix,ParameterValue="coa" \
        ParameterKey=SourceBucketName,ParameterValue="$SOURCE_BUCKET" \
        ParameterKey=TemplatesBucketName,ParameterValue="$TEMPLATES_BUCKET" \
        ParameterKey=SourceCodeKey,ParameterValue="source.zip" \
    --capabilities CAPABILITY_IAM \
    --region "$REGION"

print_info "✓ Stack $OPERATION initiated"
echo ""

# Step 4: Wait for stack to complete
print_info "Step 4: Waiting for stack to complete..."
print_info "This may take 10-15 minutes..."
echo ""

if [ "$OPERATION" = "create-stack" ]; then
    WAIT_COMMAND="stack-create-complete"
else
    WAIT_COMMAND="stack-update-complete"
fi

aws cloudformation wait "$WAIT_COMMAND" \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

print_info "✓ Stack deployment completed successfully!"
echo ""

# Step 5: Display outputs
print_info "Step 5: Stack Outputs:"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
print_info "Deployment complete!"
print_info ""
print_info "Next steps:"
print_info "1. Copy the LoadBalancerUrl from the outputs above"
print_info "2. Update your frontend configuration with the backend URL"
print_info "3. Upload source code to trigger the CI/CD pipeline:"
print_info "   aws s3 cp source.zip s3://$SOURCE_BUCKET/"
print_info ""
print_info "Monitor the pipeline:"
print_info "   aws codepipeline get-pipeline-state --name ${STACK_NAME}-pipeline --region $REGION"
print_info ""
print_info "View logs:"
print_info "   aws logs tail /ecs/$STACK_NAME/backend --follow --region $REGION"
