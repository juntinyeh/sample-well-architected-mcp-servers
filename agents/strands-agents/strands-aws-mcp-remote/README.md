# Remote AWS MCP Server Agent

This Strands agent integrates with a remote AWS MCP (Model Context Protocol) server to provide AWS operations capabilities without embedding the MCP server locally.

## Overview

Unlike the `strands-aws-api` agent which embeds an AWS MCP server locally, this agent connects to a remote MCP server instance. This approach offers several advantages:

- **Centralized MCP Server**: Single MCP server instance serves multiple agents
- **Resource Efficiency**: No need to embed MCP server in each agent
- **Easier Updates**: Update MCP server independently from agents
- **Better Scalability**: MCP server can be scaled independently

## Architecture

```
┌─────────────────────────────────────┐
│  Strands Agent                      │
│  (strands-aws-mcp-remote)           │
│                                     │
│  - Request Analysis                 │
│  - Permission Validation            │
│  - Command Formatting               │
└──────────────┬──────────────────────┘
               │
               │ MCP Protocol (HTTP/SSE)
               │
               ▼
┌─────────────────────────────────────┐
│  Remote AWS MCP Server              │
│  (Hosted on AgentCore Gateway       │
│   or separate infrastructure)       │
│                                     │
│  - AWS CLI Integration              │
│  - State Management                 │
│  - Error Handling                   │
└──────────────┬──────────────────────┘
               │
               │ AWS API Calls
               │
               ▼
┌─────────────────────────────────────┐
│  AWS Services                       │
│  (EC2, S3, Lambda, RDS, etc.)       │
└─────────────────────────────────────┘
```

## Remote MCP Server Configuration

The agent connects to a remote AWS MCP server using:

### Environment Variables

```bash
# Required: Remote MCP server URL
export AWS_MCP_SERVER_URL="https://mcp-server.example.com"

# Optional: Authentication token
export AWS_MCP_AUTH_TOKEN="your-auth-token"

# Optional: AgentCore Gateway settings
export AGENTCORE_GATEWAY_ID="gateway-id"
export AGENTCORE_GATEWAY_REGION="us-east-1"
```

### AgentCore Configuration

Create `.bedrock_agentcore.yaml` (not committed to git):

```yaml
default_agent: remote_aws_mcp

agents:
  remote_aws_mcp:
    name: remote_aws_mcp
    entrypoint: /path/to/main.py
    platform: linux/amd64
    container_runtime: docker
    
    aws:
      execution_role: arn:aws:iam::ACCOUNT:role/AgentCoreRole
      execution_role_auto_create: true
      account: 'ACCOUNT_ID'
      region: us-east-1
      ecr_repository: ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/remote-aws-mcp
      ecr_auto_create: true
      
      network_configuration:
        network_mode: PUBLIC  # Or VPC for private MCP server
        
      protocol_configuration:
        server_protocol: HTTP
        
    bedrock_agentcore:
      agent_id: remote-aws-mcp-xxxxx
      agent_arn: arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/remote-aws-mcp-xxxxx
      
    # Remote MCP server connection via AgentCore Gateway
    gateway_configuration:
      gateway_id: your-gateway-id
      target_type: MCP_SERVER
      target_url: ${AWS_MCP_SERVER_URL}
      authentication:
        type: IAM_ROLE
```

## Agent Capabilities

### 1. Request Analysis
```python
analyze_request_for_aws_operations("List all EC2 instances in us-east-1")
```

Analyzes user requests to determine:
- Required AWS services
- Operations needed
- Permission requirements
- Cost and security implications

### 2. Command Formatting
```python
format_aws_cli_command(
    service="ec2",
    operation="describe-instances",
    parameters={"region": "us-east-1"}
)
```

Formats AWS CLI commands for the remote MCP server.

### 3. Permission Validation
```python
validate_aws_permissions(
    service="s3",
    operations=["ListBuckets", "GetBucketLocation"]
)
```

Validates IAM permissions before execution.

## Usage

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export AWS_MCP_SERVER_URL="http://localhost:3000"

# Run the agent
python main.py
```

### Deployment to AgentCore

```bash
# Deploy using AgentCore CLI
agentcore deploy --config .bedrock_agentcore.yaml

# Or deploy via deploy-coa.sh
cd /path/to/sample-well-architected-mcp-servers
./deploy-coa.sh --agentcore-only
```

## Integration with COA Web Interface

The agent is automatically discovered by the COA web interface backend through:

1. **AgentCore Discovery Service**: Scans Parameter Store for registered agents
2. **Agent Registration**: Agent metadata is stored in SSM parameters
3. **Dynamic Selection**: Users can select this agent for AWS operations

### Backend Integration

```python
# In backend/agentcore/services/strands_agent_discovery_service.py
discovered_agents = await discovery_service.discover_agents()

# Agent appears in available agents list
{
    "agent_id": "remote_aws_mcp",
    "name": "Remote AWS MCP Agent",
    "description": "Remote AWS MCP Server Integration",
    "capabilities": ["aws_operations", "remote_mcp_integration"],
    "status": "HEALTHY"
}
```

## Comparison with strands-aws-api

| Feature | strands-aws-api | strands-aws-mcp-remote |
|---------|----------------|------------------------|
| **MCP Server** | Embedded locally | Remote connection |
| **Resource Usage** | Higher (embedded server) | Lower (shared server) |
| **Deployment** | Single container | Agent + separate MCP server |
| **Scalability** | Limited to agent scale | MCP server scales independently |
| **Updates** | Requires agent rebuild | MCP server updates separately |
| **Latency** | Lower (local) | Slightly higher (network) |
| **Use Case** | Standalone agent | Multi-agent environments |

## Remote MCP Server Deployment Options

### Option 1: AgentCore Gateway + Lambda

Deploy AWS MCP server as Lambda function behind AgentCore Gateway:

```bash
# Create Lambda function with AWS MCP server
aws lambda create-function \
  --function-name aws-mcp-server \
  --runtime python3.11 \
  --handler handler.lambda_handler \
  --role arn:aws:iam::ACCOUNT:role/LambdaExecutionRole

# Create AgentCore Gateway target
aws bedrock-agentcore create-gateway-target \
  --gateway-id $GATEWAY_ID \
  --target-type MCP_SERVER \
  --target-config '{"lambda_arn": "arn:aws:lambda:REGION:ACCOUNT:function:aws-mcp-server"}'
```

### Option 2: AgentCore Runtime

Deploy AWS MCP server as its own AgentCore agent:

```bash
# Deploy MCP server agent
cd /path/to/aws-mcp-server
agentcore deploy

# Connect remote agent to MCP server agent via Gateway
```

### Option 3: ECS/EKS

Deploy AWS MCP server on ECS or EKS:

```bash
# Deploy to ECS
aws ecs create-service \
  --cluster mcp-cluster \
  --service-name aws-mcp-server \
  --task-definition aws-mcp-server:1

# Expose via ALB and connect agents
```

## Security Considerations

- **Authentication**: Use IAM roles for MCP server authentication
- **Encryption**: Use TLS for MCP server communication
- **Authorization**: Implement fine-grained permissions
- **Audit Logging**: Enable CloudTrail for all operations
- **Network Security**: Use VPC for private MCP server deployment

## Troubleshooting

### Connection Issues

```bash
# Test MCP server connectivity
curl -X POST $AWS_MCP_SERVER_URL/mcp/initialize

# Check AgentCore Gateway status
aws bedrock-agentcore describe-gateway --gateway-id $GATEWAY_ID
```

### Permission Errors

```bash
# Verify IAM role permissions
aws iam get-role-policy --role-name AgentCoreRole --policy-name MCPServerAccess

# Check CloudTrail for denied API calls
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRole
```

## References

- [AWS MCP Server Documentation](https://docs.aws.amazon.com/aws-mcp/latest/userguide/getting-started-aws-mcp-server.html)
- [AgentCore Gateway Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-MCPservers.html)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Strands Agents Framework](https://github.com/anthropics/strands)

## License

MIT No Attribution - See LICENSE file in repository root.
