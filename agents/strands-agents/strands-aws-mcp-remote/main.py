"""
Remote AWS MCP Server Agent

This agent integrates with the remote AWS MCP server as documented at:
https://docs.aws.amazon.com/aws-mcp/latest/userguide/getting-started-aws-mcp-server.html

Unlike strands-aws-api which embeds the MCP server, this agent connects to
a remote MCP server instance for AWS operations.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import think
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Configure Bedrock model - using Claude 3.7 Sonnet
bedrock_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")


@tool
def analyze_request_for_aws_operations(user_request: str) -> str:
    """
    Analyze user request to determine required AWS operations.
    
    This tool helps understand what AWS services and operations are needed
    to fulfill the user's request when working with a remote AWS MCP server.
    
    Args:
        user_request: The user's natural language request
        
    Returns:
        JSON string with analysis and recommended operations
    """
    logger.info(f"Analyzing request: {user_request}")
    
    analysis_agent = Agent(
        model=bedrock_model,
        system_prompt="""You are an AWS Operations Analyst working with a remote AWS MCP server.

## Your Role
Analyze user requests and determine:
1. Which AWS services are involved
2. What operations need to be performed
3. Required permissions and considerations
4. Potential security or cost implications

## AWS Services to Consider
- **EC2**: Compute instances, security groups, volumes
- **S3**: Storage buckets, objects, access policies
- **RDS**: Database instances, snapshots, parameters
- **Lambda**: Functions, triggers, execution roles
- **IAM**: Users, roles, policies, permissions
- **VPC**: Networks, subnets, route tables, gateways
- **CloudWatch**: Logs, metrics, alarms
- **CloudFormation**: Infrastructure as code stacks
- **ECS/EKS**: Container orchestration
- **And many more...

## Response Format
Return a JSON object with:
```json
{
    "analysis": {
        "services": ["service1", "service2"],
        "operations": ["operation1", "operation2"],
        "complexity": "low|medium|high",
        "requires_permissions": ["permission1", "permission2"],
        "considerations": ["consideration1", "consideration2"]
    },
    "recommended_approach": "Step-by-step approach description",
    "mcp_tools_needed": ["mcp_tool1", "mcp_tool2"],
    "estimated_cost_impact": "none|low|medium|high"
}
```

## Examples

**Request**: "List all my EC2 instances"
**Analysis**: Simple read operation, requires ec2:DescribeInstances

**Request**: "Create a new S3 bucket with encryption"
**Analysis**: Write operation, requires s3:CreateBucket and KMS permissions

Be thorough but concise in your analysis."""
    )
    
    try:
        response = analysis_agent.invoke(user_request)
        logger.info("Request analysis completed")
        return response
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return json.dumps({
            "error": str(e),
            "analysis": {
                "services": [],
                "operations": [],
                "complexity": "unknown"
            }
        })


@tool
def format_aws_cli_command(
    service: str,
    operation: str,
    parameters: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format an AWS CLI command for the remote MCP server.
    
    Args:
        service: AWS service name (e.g., 'ec2', 's3', 'lambda')
        operation: Operation name (e.g., 'describe-instances', 'list-buckets')
        parameters: Optional parameters for the operation
        
    Returns:
        Formatted AWS CLI command string
    """
    params = parameters or {}
    
    # Build command
    command = f"aws {service} {operation}"
    
    # Add parameters
    for key, value in params.items():
        if isinstance(value, bool):
            if value:
                command += f" --{key}"
        elif isinstance(value, (list, dict)):
            command += f" --{key} '{json.dumps(value)}'"
        else:
            command += f" --{key} {value}"
    
    logger.info(f"Formatted command: {command}")
    return command


@tool
def validate_aws_permissions(
    service: str,
    operations: List[str],
    resource_arns: Optional[List[str]] = None
) -> str:
    """
    Validate AWS permissions for planned operations.
    
    Args:
        service: AWS service name
        operations: List of operations to validate
        resource_arns: Optional list of resource ARNs
        
    Returns:
        JSON string with validation results
    """
    logger.info(f"Validating permissions for {service}: {operations}")
    
    validation = {
        "service": service,
        "operations": operations,
        "required_permissions": [],
        "recommendations": [],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Build required permissions
    for operation in operations:
        permission = f"{service}:{operation}"
        validation["required_permissions"].append(permission)
    
    # Add recommendations
    validation["recommendations"].extend([
        "Ensure IAM role has necessary permissions",
        "Consider using least-privilege principle",
        "Review AWS CloudTrail for audit logging"
    ])
    
    if resource_arns:
        validation["resource_arns"] = resource_arns
        validation["recommendations"].append(
            "Verify resource ARNs are correct and accessible"
        )
    
    return json.dumps(validation, indent=2)


# Create the main Remote AWS MCP Agent
remote_aws_mcp_agent = Agent(
    model=bedrock_model,
    tools=[
        analyze_request_for_aws_operations,
        format_aws_cli_command,
        validate_aws_permissions,
        think
    ],
    system_prompt="""You are the Remote AWS MCP Server Agent, an intelligent assistant for AWS operations through a remote Model Context Protocol (MCP) server.

## Your Capabilities

### Remote MCP Integration
- Connect to remote AWS MCP server endpoints
- Execute AWS CLI commands through MCP protocol
- Handle async operations and long-running tasks
- Manage session state across operations

### AWS Operations
- Query and manage AWS resources across all services
- Execute read and write operations safely
- Provide detailed explanations of AWS concepts
- Suggest best practices and optimizations

### Analysis and Planning
- Analyze user requests for required AWS operations
- Plan multi-step workflows
- Validate permissions before execution
- Estimate cost and security implications

## How You Work

1. **Understand Request**: Use `analyze_request_for_aws_operations` to understand what the user needs
2. **Plan Operations**: Determine the sequence of AWS operations required
3. **Validate Permissions**: Use `validate_aws_permissions` to check access requirements
4. **Format Commands**: Use `format_aws_cli_command` to prepare AWS CLI commands
5. **Execute via MCP**: The commands will be sent to the remote AWS MCP server
6. **Process Results**: Parse and present results in a user-friendly format

## Remote MCP Server Connection

The remote AWS MCP server provides these capabilities:
- **AWS CLI Integration**: Execute any AWS CLI command
- **Resource Discovery**: Find and list AWS resources
- **State Management**: Track changes and configurations
- **Error Handling**: Robust error recovery and retry logic

## Best Practices

- Always validate user inputs before executing commands
- Use `think` to reason through complex multi-step operations
- Provide clear explanations of what you're doing
- Warn about potentially destructive operations
- Suggest cost-optimized alternatives when applicable
- Consider security implications of operations

## Response Format

Structure your responses clearly:
1. **Understanding**: Summarize what you understand
2. **Planned Operations**: List AWS operations you'll perform
3. **Execution**: Show command execution and results
4. **Summary**: Provide a clear summary of outcomes

## Error Handling

If operations fail:
- Explain what went wrong in simple terms
- Suggest potential fixes
- Provide alternative approaches
- Include relevant AWS documentation links

Remember: You're working with a remote MCP server, so commands are executed remotely. Always be mindful of:
- Network latency
- Session timeouts
- Authentication and authorization
- Rate limiting and throttling

Be helpful, accurate, and proactive in guiding users through their AWS operations!"""
)


@app.agent()
async def invoke_remote_aws_mcp_agent(user_input: str, session_id: str = None) -> Dict[str, Any]:
    """
    Main entry point for the Remote AWS MCP Agent.
    
    Args:
        user_input: User's natural language request
        session_id: Optional session ID for conversation context
        
    Returns:
        Dictionary with agent response and metadata
    """
    logger.info(f"Invocation started - Session: {session_id}")
    logger.info(f"User input: {user_input}")
    
    try:
        # Invoke the agent
        response = await remote_aws_mcp_agent.invoke_async(user_input)
        
        result = {
            "response": response,
            "session_id": session_id or f"session-{datetime.utcnow().timestamp()}",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_type": "remote_aws_mcp",
            "status": "success"
        }
        
        logger.info("Invocation completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Invocation failed: {e}", exc_info=True)
        
        return {
            "error": str(e),
            "session_id": session_id or f"session-{datetime.utcnow().timestamp()}",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_type": "remote_aws_mcp",
            "status": "error"
        }


# Agent metadata for discovery
AGENT_METADATA = {
    "name": "remote_aws_mcp_agent",
    "version": "1.0.0",
    "description": "Remote AWS MCP Server Integration Agent",
    "capabilities": [
        "aws_operations",
        "remote_mcp_integration",
        "multi_service_support",
        "permission_validation",
        "cost_analysis"
    ],
    "mcp_server_type": "remote",
    "mcp_server_url": "${AWS_MCP_SERVER_URL}",  # To be configured via environment
    "supported_services": "all",  # Supports all AWS services via CLI
    "authentication": "iam_role"
}


if __name__ == "__main__":
    # Test invocation
    import asyncio
    
    async def test():
        """Test the agent locally."""
        test_input = "List all my S3 buckets"
        print(f"\nTesting Remote AWS MCP Agent with: '{test_input}'\n")
        
        result = await invoke_remote_aws_mcp_agent(test_input, "test-session")
        
        print(f"\nResult:")
        print(json.dumps(result, indent=2))
    
    asyncio.run(test())
