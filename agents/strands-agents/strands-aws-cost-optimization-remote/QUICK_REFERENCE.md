# Quick Reference Guide

## Overview

AWS Cost Optimization Agent with Remote MCP Server Integration
- **Location:** `agents/strands-agents/strands-aws-cost-optimization-remote/`
- **Purpose:** Cost optimization and billing management via remote AWS managed API MCP server
- **Features:** Prompt validation, task restructuring, long-running support (8 hours)

## Quick Start

### 1. Prerequisites
```bash
# AWS credentials configured
aws sts get-caller-identity

# Required services access
# - Amazon Bedrock (Claude 3.5 Sonnet)
# - AWS Systems Manager Parameter Store
# - Bedrock AgentCore Runtime
```

### 2. Configuration
```bash
# Set SSM parameter with MCP connection info
aws ssm put-parameter \
  --name "/coa/components/aws_api_mcp/connection_info" \
  --type "String" \
  --value '{"agent_arn":"arn:aws:bedrock:...","agent_id":"..."}' \
  --overwrite
```

### 3. Environment Variables
```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0
export ENABLE_LONG_RUNNING=true
export LOG_LEVEL=INFO
```

### 4. Deployment
```bash
# Build package
pip install -r requirements.txt -t package/
cp main.py config.py package/
cd package && zip -r ../agent.zip . && cd ..

# Deploy to Bedrock AgentCore Runtime
# (Follow DEPLOYMENT.md for detailed steps)
```

## Key Features

### ✅ Prompt Validation
```python
# Blocks malicious patterns
- SQL injection (UNION SELECT, DROP TABLE)
- Command injection (;, &&, ||, backticks)
- Sensitive data (AWS keys, passwords)
- Excessive length (max 10,000 chars)
```

### ✅ Task Restructuring
```python
# Transforms queries into MCP operations
{
  "analysis": {"complexity": "multi", "duration": "long"},
  "operations": [
    {"mcp_tool": "aws___run_aws_cli", "mcp_arguments": {...}}
  ]
}
```

### ✅ Remote MCP Integration
```python
# Connects via Bedrock AgentCore Runtime
URL: https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations
Method: HTTPS with async streaming
Config: SSM Parameter Store
```

### ✅ Long-Running Support
```python
# Duration-based timeouts
short:  300s   (5 minutes)
medium: 1800s  (30 minutes)
long:   28800s (8 hours)
```

## Common Commands

### Test Validation
```python
from main import validate_prompt
result = validate_prompt("Show EC2 costs for last month")
print(f"Valid: {result['is_valid']}")
```

### Test Preprocessing
```python
from main import preprocess_and_validate_prompt
result = preprocess_and_validate_prompt.fn("Complex cost analysis query")
import json
analysis = json.loads(result)
print(f"Complexity: {analysis['analysis']['complexity']}")
```

### Run Example Tests
```bash
python3 example_usage.py
```

### Verify Installation
```bash
./verify.sh
```

## Tools Available

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `preprocess_and_validate_prompt` | Validate & analyze | Query string | Validation + Analysis JSON |
| `execute_cost_optimization_workflow` | Multi-op orchestration | Analysis JSON | Aggregated results |
| `query_cost_optimization_mcp` | Direct MCP query | AWS CLI command | MCP response |
| `think` | Strategy planning | Context | Analysis |

## File Structure

```
strands-aws-cost-optimization-remote/
├── main.py                      # Main agent (700 lines)
├── config.py                    # Configuration (120 lines)
├── requirements.txt             # Dependencies (46 packages)
├── Dockerfile                   # Container config
├── README.md                    # User guide (278 lines)
├── DEPLOYMENT.md                # Deployment guide (508 lines)
├── LONG_RUNNING_SUPPORT.md      # Long-running guide (385 lines)
├── COMPARISON.md                # Legacy vs Remote (430 lines)
├── IMPLEMENTATION_SUMMARY.md    # Implementation details (380 lines)
├── example_usage.py             # Usage examples (200 lines)
├── verify.sh                    # Verification script
└── .gitignore                   # Git ignore patterns
```

## Troubleshooting

### Connection Errors
```bash
# Check SSM parameter
aws ssm get-parameter --name "/coa/components/aws_api_mcp/connection_info"

# Verify MCP server is running
aws bedrock-runtime invoke-agent --agent-id <mcp-agent-id> ...
```

### Validation Failures
```bash
# Check blocked patterns in validation result
# Remove or escape special characters
# Ensure input length < 10,000 characters
```

### Timeout Issues
```bash
# For long operations, verify:
export ENABLE_LONG_RUNNING=true
export TIMEOUT_LONG=28800

# Check session timeout in agent config (480 minutes)
```

### Permission Errors
```bash
# Verify IAM role has required permissions:
- bedrock:InvokeModel
- ssm:GetParameter
- logs:CreateLogStream, PutLogEvents
- bedrock:InvokeAgent
```

## Example Queries

### Simple Query
```
Show me Lambda costs for the last month
```
**Expected:** Direct MCP query, ~30 seconds

### Medium Complexity
```
Analyze EC2, S3, and RDS costs for Q4 with month-over-month comparison
```
**Expected:** Multi-operation workflow, ~5-10 minutes

### Long-Running
```
Perform comprehensive cost optimization audit across all accounts:
- 12 months historical analysis
- Trend forecasting for next quarter
- Rightsizing recommendations for all compute
- Reserved Instance opportunities
- Storage optimization recommendations
```
**Expected:** Long-running workflow, 2-6 hours

## Security Best Practices

1. ✅ **Never disable validation** in production
2. ✅ **Use SSM Parameter Store** for sensitive config
3. ✅ **Enable CloudWatch Logs** for audit trail
4. ✅ **Use least privilege IAM roles**
5. ✅ **Review validation warnings** in logs

## Performance Tips

1. **Break large queries** into smaller operations
2. **Use duration estimation** to set expectations
3. **Enable caching** for repeated queries (future enhancement)
4. **Monitor CloudWatch metrics** for optimization opportunities

## Support Resources

- **Full Documentation:** README.md
- **Deployment Guide:** DEPLOYMENT.md
- **Long-Running Guide:** LONG_RUNNING_SUPPORT.md
- **Comparison with Legacy:** COMPARISON.md
- **Implementation Details:** IMPLEMENTATION_SUMMARY.md
- **Testing:** example_usage.py
- **Verification:** verify.sh

## Quick Links

- AWS Bedrock AgentCore: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/
- Long-Running Ops: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html
- MCP Specification: https://modelcontextprotocol.io/
- AWS Cost Management: https://aws.amazon.com/aws-cost-management/

## Getting Help

1. Check logs: `aws logs tail /aws/bedrock/agentcore/cost-optimization-agent-remote`
2. Run verification: `./verify.sh`
3. Test examples: `python3 example_usage.py`
4. Review troubleshooting section in README.md

---

**Version:** 1.0.0
**Last Updated:** 2025-01-07
**Status:** ✅ Production Ready
