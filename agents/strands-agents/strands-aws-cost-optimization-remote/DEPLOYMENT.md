# Deployment Guide

This guide provides step-by-step instructions for deploying the AWS Cost Optimization Agent with Remote MCP Server to AWS Bedrock AgentCore Runtime.

## Prerequisites

### 1. AWS Account Setup
- AWS account with appropriate permissions
- AWS CLI installed and configured
- IAM role for Bedrock AgentCore Runtime

### 2. Required Services
- Amazon Bedrock access (Claude 3.5 Sonnet)
- AWS Systems Manager Parameter Store
- AWS Bedrock AgentCore Runtime
- CloudWatch Logs

### 3. MCP Server Deployment
The remote AWS API MCP server must be deployed first. See the MCP server deployment guide in the repository.

## Deployment Steps

### Step 1: Configure SSM Parameters

Create the SSM parameter for MCP connection information:

```bash
# Set your AWS region
export AWS_REGION=us-east-1

# Set the MCP server connection info
aws ssm put-parameter \
  --name "/coa/components/aws_api_mcp/connection_info" \
  --type "String" \
  --value '{
    "agent_arn": "arn:aws:bedrock:us-east-1:ACCOUNT_ID:agent/AGENT_ID",
    "agent_id": "AGENT_ID",
    "package_name": "awslabs.aws-api-mcp-server"
  }' \
  --description "Connection info for AWS API MCP Server" \
  --overwrite
```

Replace:
- `ACCOUNT_ID`: Your AWS account ID
- `AGENT_ID`: The deployed MCP server's agent ID

### Step 2: Create IAM Role

Create an IAM role for the agent with required permissions:

```bash
# Create trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name CostOptimizationAgentRole \
  --assume-role-policy-document file://trust-policy.json

# Create permissions policy
cat > permissions-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": [
        "arn:aws:ssm:*:*:parameter/coa/components/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": [
        "arn:aws:logs:*:*:log-group:/aws/bedrock/agentcore/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeAgent"
      ],
      "Resource": [
        "arn:aws:bedrock:*:*:agent/*"
      ]
    }
  ]
}
EOF

# Attach the policy
aws iam put-role-policy \
  --role-name CostOptimizationAgentRole \
  --policy-name CostOptimizationAgentPolicy \
  --policy-document file://permissions-policy.json
```

### Step 3: Build and Package

Build the agent package:

```bash
# Navigate to agent directory
cd agents/strands-agents/strands-aws-cost-optimization-remote

# Create package directory
mkdir -p package

# Install dependencies to package directory
pip install -r requirements.txt -t package/

# Copy application files
cp main.py package/
cp config.py package/

# Create deployment package
cd package
zip -r ../cost-optimization-agent.zip .
cd ..
```

### Step 4: Deploy to Bedrock AgentCore Runtime

Create the agent configuration:

```bash
# Create agent configuration file
cat > agent-config.json <<EOF
{
  "agentName": "cost-optimization-agent-remote",
  "description": "AWS Cost Optimization Agent with Remote MCP Server Integration",
  "agentResourceRoleArn": "arn:aws:iam::ACCOUNT_ID:role/CostOptimizationAgentRole",
  "foundationModel": "anthropic.claude-3-7-sonnet-20250219-v1:0",
  "instruction": "You are an AWS Cost Optimization and Billing Management Specialist.",
  "sessionIdleTimeoutInMinutes": 480
}
EOF

# Deploy the agent
aws bedrock-agent create-agent \
  --cli-input-json file://agent-config.json \
  --region $AWS_REGION
```

**Note:** The `sessionIdleTimeoutInMinutes: 480` (8 hours) enables long-running operation support.

### Step 5: Upload Agent Code

Upload the agent code to Bedrock AgentCore:

```bash
# Get the agent ID from previous step output
export AGENT_ID=<agent-id-from-create-agent>

# Create agent version
aws bedrock-agent create-agent-version \
  --agent-id $AGENT_ID \
  --region $AWS_REGION

# Upload the package (method depends on Bedrock AgentCore Runtime specifics)
# Follow AWS documentation for code upload procedures
```

### Step 6: Configure Environment Variables

Set environment variables in the runtime configuration:

```json
{
  "environment": {
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "MCP_SSM_PARAMETER": "/coa/components/aws_api_mcp/connection_info",
    "ENABLE_LONG_RUNNING": "true",
    "MAX_OPERATION_DURATION": "28800",
    "TIMEOUT_SHORT": "300",
    "TIMEOUT_MEDIUM": "1800",
    "TIMEOUT_LONG": "28800",
    "LOG_LEVEL": "INFO",
    "ENABLE_INPUT_VALIDATION": "true",
    "MAX_INPUT_LENGTH": "10000"
  }
}
```

### Step 7: Test Deployment

Test the deployed agent:

```bash
# Create test payload
cat > test-payload.json <<EOF
{
  "prompt": "Show me EC2 costs for the last month",
  "sessionId": "test-session-001"
}
EOF

# Invoke the agent
aws bedrock-runtime invoke-agent \
  --agent-id $AGENT_ID \
  --agent-alias-id TSTALIASID \
  --session-id test-session-001 \
  --input-text "Show me EC2 costs for the last month" \
  --region $AWS_REGION \
  test-output.json

# Check output
cat test-output.json
```

## Verification

### 1. Check CloudWatch Logs

View agent logs:

```bash
# Get log group name
LOG_GROUP="/aws/bedrock/agentcore/cost-optimization-agent-remote"

# View recent logs
aws logs tail $LOG_GROUP --follow --region $AWS_REGION
```

Expected log entries:
```
[INFO] Received user input: Show me EC2 costs for the last month
[INFO] Session ID: test-session-001
[INFO] Executing 1 cost optimization operations using sequential strategy
[INFO] ✅ Operation 1 completed successfully
```

### 2. Verify SSM Parameters

```bash
# Verify connection info parameter exists
aws ssm get-parameter \
  --name "/coa/components/aws_api_mcp/connection_info" \
  --region $AWS_REGION
```

### 3. Test with Various Queries

```bash
# Test simple query
aws bedrock-runtime invoke-agent \
  --agent-id $AGENT_ID \
  --agent-alias-id TSTALIASID \
  --session-id test-simple \
  --input-text "Show Lambda costs for last week" \
  --region $AWS_REGION \
  simple-test.json

# Test complex workflow
aws bedrock-runtime invoke-agent \
  --agent-id $AGENT_ID \
  --agent-alias-id TSTALIASID \
  --session-id test-complex \
  --input-text "Perform comprehensive cost optimization analysis" \
  --region $AWS_REGION \
  complex-test.json

# Test long-running operation
aws bedrock-runtime invoke-agent \
  --agent-id $AGENT_ID \
  --agent-alias-id TSTALIASID \
  --session-id test-long \
  --input-text "Analyze cost trends for past 12 months and forecast next quarter" \
  --region $AWS_REGION \
  long-test.json
```

## Configuration Updates

### Update SSM Parameters

```bash
# Update MCP connection info
aws ssm put-parameter \
  --name "/coa/components/aws_api_mcp/connection_info" \
  --type "String" \
  --value '{"agent_arn": "...", "agent_id": "..."}' \
  --overwrite

# No restart needed - parameters are fetched dynamically
```

### Update Agent Code

```bash
# Build new package
./build-package.sh

# Create new agent version
aws bedrock-agent create-agent-version \
  --agent-id $AGENT_ID \
  --region $AWS_REGION

# Upload updated package
# Follow Bedrock AgentCore Runtime update procedures
```

## Monitoring

### CloudWatch Dashboards

Create a dashboard for monitoring:

```bash
cat > dashboard-config.json <<EOF
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Bedrock", "InvocationCount", {"stat": "Sum"}],
          [".", "InvocationLatency", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Agent Invocations"
      }
    }
  ]
}
EOF

aws cloudwatch put-dashboard \
  --dashboard-name CostOptimizationAgent \
  --dashboard-body file://dashboard-config.json
```

### CloudWatch Alarms

Set up alarms for monitoring:

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name cost-optimization-agent-high-errors \
  --alarm-description "Alert when agent error rate is high" \
  --metric-name Errors \
  --namespace AWS/Bedrock \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# Long operation timeout alarm
aws cloudwatch put-metric-alarm \
  --alarm-name cost-optimization-agent-timeouts \
  --alarm-description "Alert when operations timeout" \
  --metric-name Timeouts \
  --namespace AWS/Bedrock \
  --statistic Sum \
  --period 3600 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```

## Troubleshooting

### Agent Won't Start

**Check:**
1. IAM role has correct permissions
2. SSM parameters are configured
3. MCP server is deployed and accessible
4. CloudWatch logs for error messages

**Solution:**
```bash
# Check IAM role
aws iam get-role --role-name CostOptimizationAgentRole

# Verify SSM parameter
aws ssm get-parameter --name "/coa/components/aws_api_mcp/connection_info"

# Check CloudWatch logs
aws logs tail /aws/bedrock/agentcore/cost-optimization-agent-remote
```

### MCP Connection Failures

**Check:**
1. MCP server agent ARN is correct
2. Network connectivity to Bedrock AgentCore Runtime
3. IAM permissions for invoking MCP server

**Solution:**
```bash
# Test MCP server directly
aws bedrock-runtime invoke-agent \
  --agent-id <mcp-agent-id> \
  --session-id test \
  --input-text '{"tool": "aws___run_aws_cli", "args": {"command": "ce help"}}' \
  mcp-test.json
```

### Timeout Issues

**For long operations:**
1. Verify `ENABLE_LONG_RUNNING=true`
2. Check `sessionIdleTimeoutInMinutes` is set to 480
3. Ensure operation duration estimate is correct

**Solution:**
```bash
# Update agent configuration with longer timeout
aws bedrock-agent update-agent \
  --agent-id $AGENT_ID \
  --session-idle-timeout-in-minutes 480
```

## Cleanup

To remove the deployment:

```bash
# Delete agent
aws bedrock-agent delete-agent \
  --agent-id $AGENT_ID \
  --region $AWS_REGION

# Remove IAM role and policies
aws iam delete-role-policy \
  --role-name CostOptimizationAgentRole \
  --policy-name CostOptimizationAgentPolicy

aws iam delete-role \
  --role-name CostOptimizationAgentRole

# Remove SSM parameters
aws ssm delete-parameter \
  --name "/coa/components/aws_api_mcp/connection_info"

# Delete CloudWatch log groups
aws logs delete-log-group \
  --log-group-name /aws/bedrock/agentcore/cost-optimization-agent-remote
```

## Security Considerations

1. **IAM Permissions**: Use least privilege principle
2. **SSM Parameters**: Use SecureString for sensitive data
3. **Network Security**: Ensure MCP endpoints are secured
4. **Audit Logging**: Enable CloudTrail for all operations
5. **Data Protection**: No sensitive data in logs

## Best Practices

1. **Version Control**: Tag each deployment with version
2. **Testing**: Test in non-production environment first
3. **Monitoring**: Set up comprehensive monitoring before production
4. **Documentation**: Keep deployment documentation updated
5. **Backup**: Maintain backups of configuration and code

## Support

For issues or questions:
1. Check CloudWatch Logs for detailed error messages
2. Review this deployment guide
3. Consult AWS Bedrock AgentCore Runtime documentation
4. Open an issue in the repository

## References

- [AWS Bedrock AgentCore Runtime Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [AWS CLI Reference for Bedrock](https://docs.aws.amazon.com/cli/latest/reference/bedrock/)
- [CloudWatch Logs Documentation](https://docs.aws.amazon.com/cloudwatch/latest/logs/)
- [SSM Parameter Store Guide](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
