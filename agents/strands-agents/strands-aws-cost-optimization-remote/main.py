"""
AWS Cost Optimization Agent with Remote MCP Server Integration

This module provides an AWS cost and billing management agent that connects to
a remote AWS managed API MCP server via Bedrock AgentCore runtime. It includes
intelligent prompt preprocessing, task restructuring for MCP compatibility, and
support for long-running operations up to 8 hours.
"""

import os
import re
import json
import boto3
import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import timedelta

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import think
from bedrock_agentcore.runtime import BedrockAgentCoreApp


# Initialize the Bedrock AgentCore App
app = BedrockAgentCoreApp()

# Configure the Bedrock model
bedrock_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")


def get_ssm_parameter(parameter_name: str, region: str = None) -> Optional[str]:
    """
    Retrieve a parameter from AWS Systems Manager Parameter Store.
    
    Args:
        parameter_name: The name of the SSM parameter
        region: AWS region (defaults to AWS_REGION environment variable or us-east-1)
        
    Returns:
        The parameter value as a string, or None if not found
    """
    if region is None:
        region = os.getenv("AWS_REGION", "us-east-1")
    
    try:
        ssm_client = boto3.client("ssm", region_name=region)
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error retrieving SSM parameter {parameter_name}: {e}")
        return None


def get_mcp_connection_info(region: str = None) -> Optional[Dict[str, Any]]:
    """
    Get MCP server connection information from SSM Parameter Store.
    
    Args:
        region: AWS region (defaults to AWS_REGION environment variable or us-east-1)
        
    Returns:
        Dictionary containing connection info (agent_arn, agent_id, etc.) or None
    """
    param_value = get_ssm_parameter("/coa/components/aws_api_mcp/connection_info", region)
    if param_value:
        try:
            return json.loads(param_value)
        except json.JSONDecodeError as e:
            print(f"Error parsing connection info JSON: {e}")
    return None


async def call_remote_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    region: str = None,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    Call a tool on the remote AWS API MCP server via Bedrock AgentCore runtime.
    
    Args:
        tool_name: Name of the MCP tool to call
        arguments: Dictionary of arguments for the tool
        region: AWS region for the MCP server
        timeout: Timeout in seconds for the operation
        
    Returns:
        Dictionary with success status and result data
    """
    if region is None:
        region = os.getenv("AWS_REGION", "us-east-1")
    
    try:
        # Get connection info from SSM
        connection_info = get_mcp_connection_info(region)
        if not connection_info:
            return {
                "success": False,
                "error": "Failed to retrieve MCP connection info from SSM Parameter Store"
            }
        
        agent_arn = connection_info.get("agent_arn")
        if not agent_arn:
            return {
                "success": False,
                "error": "No agent_arn found in connection info"
            }
        
        # Encode ARN for URL
        encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
        mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
        mcp_headers = {"Content-Type": "application/json"}
        
        # Call the remote MCP tool
        async with streamablehttp_client(
            mcp_url,
            mcp_headers,
            timeout=timedelta(seconds=timeout)
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name=tool_name, arguments=arguments)
                
                # Extract result content
                if result.content and len(result.content) > 0:
                    return {
                        "success": True,
                        "data": result.content[0].text
                    }
                else:
                    return {
                        "success": True,
                        "data": f"Tool {tool_name} executed successfully but returned no content"
                    }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Error calling remote MCP tool {tool_name}: {str(e)}"
        }


def validate_prompt(user_input: str) -> Dict[str, Any]:
    """
    Validate and sanitize incoming user prompts before processing.
    
    This function checks for:
    - Empty or invalid inputs
    - SQL injection attempts
    - Command injection attempts
    - Sensitive data exposure patterns
    - Excessive length
    
    Args:
        user_input: The raw user input to validate
        
    Returns:
        Dictionary with validation result and sanitized input
    """
    validation_result = {
        "is_valid": True,
        "sanitized_input": user_input,
        "warnings": [],
        "blocked_patterns": []
    }
    
    # Check for empty input
    if not user_input or not user_input.strip():
        validation_result["is_valid"] = False
        validation_result["warnings"].append("Empty input provided")
        return validation_result
    
    # Check for excessive length (max 10000 characters)
    if len(user_input) > 10000:
        validation_result["is_valid"] = False
        validation_result["warnings"].append("Input exceeds maximum length of 10000 characters")
        return validation_result
    
    # Check for SQL injection patterns
    sql_patterns = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(--\s*$)",
        r"(/\*.*\*/)",
        r"(\bOR\b\s+['\"]?1['\"]?\s*=\s*['\"]?1)"
    ]
    
    for pattern in sql_patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            validation_result["warnings"].append("Potential SQL injection pattern detected")
            validation_result["blocked_patterns"].append(pattern)
    
    # Check for command injection patterns
    cmd_patterns = [
        r"[;&|`$()]",
        r"\$\(.*\)",
        r"`.*`",
        r"&&",
        r"\|\|"
    ]
    
    for pattern in cmd_patterns:
        if re.search(pattern, user_input):
            validation_result["warnings"].append("Potential command injection pattern detected")
            validation_result["blocked_patterns"].append(pattern)
    
    # Check for sensitive data patterns (AWS credentials, API keys)
    sensitive_patterns = [
        r"AKIA[0-9A-Z]{16}",  # AWS Access Key ID
        r"aws_secret_access_key\s*=",
        r"password\s*=\s*['\"]",
        r"api[_-]?key\s*=\s*['\"]"
    ]
    
    for pattern in sensitive_patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            validation_result["warnings"].append("Potential sensitive data detected in input")
            # Redact the sensitive data
            validation_result["sanitized_input"] = re.sub(
                pattern,
                "[REDACTED]",
                validation_result["sanitized_input"],
                flags=re.IGNORECASE
            )
    
    # If there are critical warnings, mark as invalid
    if validation_result["blocked_patterns"]:
        validation_result["is_valid"] = False
    
    return validation_result


@tool
def preprocess_and_validate_prompt(user_input: str) -> str:
    """
    Validate and sanitize incoming user prompts, then analyze for complexity.
    
    This tool performs two key functions:
    1. Security validation to prevent malicious inputs
    2. Complexity analysis to determine execution strategy
    
    Args:
        user_input: The raw user input that may contain multiple AWS operations
        
    Returns:
        JSON string containing validation status, sanitized input, and analysis
    """
    # First, validate the prompt
    validation_result = validate_prompt(user_input)
    
    if not validation_result["is_valid"]:
        return json.dumps({
            "validation": {
                "is_valid": False,
                "warnings": validation_result["warnings"],
                "blocked_patterns": validation_result["blocked_patterns"]
            },
            "error": "Input validation failed. Please review warnings and provide a safe input."
        })
    
    sanitized_input = validation_result["sanitized_input"]
    
    # Create a preprocessing agent to analyze the sanitized input
    preprocessing_agent = Agent(
        model=bedrock_model,
        system_prompt="""You are an AWS Cost and Billing Operations Preprocessor. Your job is to analyze user inputs related to cost optimization, billing analysis, and financial management, determining if they contain multiple operations that should be executed separately.

## Cost Analysis Framework

### Single Cost Operation Indicators:
- One clear cost metric or billing query (monthly costs, specific service spending)
- One specific financial action (get costs, list budgets, show usage, analyze spend)
- Focused financial scope (single service, single account, specific time period)
- Simple cost query structure (direct cost retrieval or basic analysis)

### Multi-Cost Operation Indicators:
- Multiple AWS services for cost analysis
- Multiple financial metrics or complex cost workflows
- Cross-service cost dependencies (e.g., "analyze EC2 costs and related EBS charges")
- Comparative cost analysis requests (e.g., "compare costs across regions and accounts")
- Sequential cost operations (e.g., "get current costs then forecast future spend")
- Comprehensive cost assessments (e.g., "analyze my entire cost optimization opportunities")
- Cost optimization workflows (rightsizing + RI recommendations + unused resources)

### Cost-Focused Parameter Detection:
Extract these parameters when present for billing and cost analysis:
- **account_id**: 12-digit AWS account numbers for cost allocation
- **role_arn**: Complete IAM role ARNs (arn:aws:iam::ACCOUNT:role/ROLE-NAME)
- **external_id**: External IDs for cross-account access
- **region**: AWS regions for regional cost analysis
- **time_period**: Cost analysis time ranges (last month, YTD, custom ranges)
- **cost_dimensions**: Service, usage type, operation filters for cost breakdown

## Response Format

Return a JSON object with this structure:
```json
{
    "analysis": {
        "complexity": "single|multi",
        "reasoning": "Brief explanation focusing on cost analysis complexity",
        "detected_services": ["ec2", "s3", "rds"],
        "detected_actions": ["get_costs", "analyze_usage", "recommend_savings"],
        "cost_focus_areas": ["rightsizing", "reserved_instances", "unused_resources"],
        "cross_account_params": {
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/RoleName",
            "external_id": "external-id-value",
            "region": "us-east-1"
        },
        "time_scope": {
            "period": "monthly|daily|custom",
            "range": "last_month|ytd|custom_range"
        },
        "estimated_duration": "short|medium|long"
    },
    "operations": [
        {
            "sequence": 1,
            "description": "Cost operation description",
            "query": "Specific cost query for AWS API MCP server",
            "dependencies": ["operation_2_output"],
            "estimated_complexity": "low|medium|high",
            "cost_impact": "potential savings or cost insights expected",
            "mcp_tool": "aws___run_aws_cli",
            "mcp_arguments": {
                "command": "ce get-cost-and-usage",
                "args": ["--time-period", "..."]
            }
        }
    ],
    "execution_strategy": "sequential|parallel|conditional"
}
```

Focus on creating actionable, cost-specific queries that can be executed via the AWS API MCP server using AWS CLI commands."""
    )
    
    try:
        analysis_result = preprocessing_agent(f"Analyze this AWS cost optimization request: {sanitized_input}")
        analysis_text = analysis_result.message['content'][0]['text']
        
        # Combine validation and analysis results
        combined_result = {
            "validation": {
                "is_valid": True,
                "warnings": validation_result["warnings"]
            },
            "sanitized_input": sanitized_input
        }
        
        # Try to parse the analysis as JSON and merge
        try:
            analysis_data = json.loads(analysis_text)
            combined_result.update(analysis_data)
        except json.JSONDecodeError:
            # If not JSON, include as raw analysis
            combined_result["analysis_raw"] = analysis_text
        
        return json.dumps(combined_result)
        
    except Exception as e:
        # Fallback to simple analysis if preprocessing fails
        return json.dumps({
            "validation": {
                "is_valid": True,
                "warnings": validation_result["warnings"]
            },
            "sanitized_input": sanitized_input,
            "analysis": {
                "complexity": "single",
                "reasoning": f"Preprocessing failed: {str(e)}, treating as single operation",
                "detected_services": [],
                "detected_actions": [],
                "cost_focus_areas": [],
                "estimated_duration": "medium"
            },
            "operations": [{
                "sequence": 1,
                "description": "Direct execution of user request",
                "query": sanitized_input,
                "dependencies": [],
                "estimated_complexity": "medium",
                "cost_impact": "unknown"
            }],
            "execution_strategy": "sequential"
        })


@tool
def execute_cost_optimization_workflow(preprocessed_analysis: str) -> str:
    """
    Execute a workflow of AWS cost optimization operations based on preprocessed analysis.
    
    This tool handles:
    - Task restructuring for MCP server compatibility
    - Sequential/parallel execution of operations
    - Long-running task support with session management
    - Cross-account parameter handling
    
    Args:
        preprocessed_analysis: JSON string from preprocess_and_validate_prompt
        
    Returns:
        Comprehensive results from all executed operations
    """
    try:
        analysis = json.loads(preprocessed_analysis)
    except json.JSONDecodeError as e:
        return f"Error parsing preprocessed analysis: {e}"
    
    # Check validation status
    validation = analysis.get("validation", {})
    if not validation.get("is_valid", True):
        return f"Cannot execute workflow - input validation failed: {validation.get('warnings', [])}"
    
    operations = analysis.get("operations", [])
    execution_strategy = analysis.get("execution_strategy", "sequential")
    estimated_duration = analysis.get("analysis", {}).get("estimated_duration", "medium")
    
    results = []
    operation_outputs = {}  # Store outputs for dependency resolution
    
    print(f"Executing {len(operations)} cost optimization operations using {execution_strategy} strategy")
    print(f"Estimated duration: {estimated_duration}")
    
    # Configure timeout based on estimated duration
    timeout_map = {
        "short": 300,      # 5 minutes
        "medium": 1800,    # 30 minutes
        "long": 28800      # 8 hours (long-running support)
    }
    operation_timeout = timeout_map.get(estimated_duration, 1800)
    
    # Use asyncio to run the workflow
    async def run_workflow():
        for operation in operations:
            sequence = operation.get("sequence", 1)
            description = operation.get("description", "AWS Cost Operation")
            query = operation.get("query", "")
            dependencies = operation.get("dependencies", [])
            mcp_tool = operation.get("mcp_tool", "aws___run_aws_cli")
            mcp_arguments = operation.get("mcp_arguments", {})
            
            print(f"\n--- Operation {sequence}: {description} ---")
            print(f"Using MCP tool: {mcp_tool}")
            
            # Check dependencies
            missing_deps = [dep for dep in dependencies if dep not in operation_outputs]
            if missing_deps:
                error_msg = f"Missing dependencies for operation {sequence}: {missing_deps}"
                print(error_msg)
                results.append({
                    "sequence": sequence,
                    "description": description,
                    "status": "failed",
                    "error": error_msg
                })
                continue
            
            # Substitute dependency outputs in arguments if needed
            enhanced_arguments = mcp_arguments.copy()
            for dep in dependencies:
                if dep in operation_outputs:
                    # Add context from previous operation
                    if "context" not in enhanced_arguments:
                        enhanced_arguments["context"] = []
                    enhanced_arguments["context"].append({
                        "dependency": dep,
                        "output": operation_outputs[dep]
                    })
            
            try:
                # Execute the remote MCP operation
                start_time = time.time()
                result = await call_remote_mcp_tool(
                    tool_name=mcp_tool,
                    arguments=enhanced_arguments,
                    timeout=operation_timeout
                )
                execution_time = time.time() - start_time
                
                if result["success"]:
                    # Store result for potential dependencies
                    operation_outputs[f"operation_{sequence}_output"] = result["data"]
                    
                    results.append({
                        "sequence": sequence,
                        "description": description,
                        "status": "success",
                        "result": result["data"],
                        "execution_time": execution_time
                    })
                    
                    print(f"✅ Operation {sequence} completed successfully in {execution_time:.2f}s")
                else:
                    error_msg = result.get("error", "Unknown error")
                    print(f"❌ Operation {sequence} failed: {error_msg}")
                    results.append({
                        "sequence": sequence,
                        "description": description,
                        "status": "failed",
                        "error": error_msg,
                        "execution_time": execution_time
                    })
                    
                    # For sequential execution, stop on first failure
                    if execution_strategy == "sequential":
                        print("Sequential execution stopped due to failure")
                        break
                
            except Exception as e:
                execution_time = time.time() - start_time if 'start_time' in locals() else 0
                error_msg = f"Operation {sequence} exception: {str(e)}"
                print(f"❌ {error_msg}")
                results.append({
                    "sequence": sequence,
                    "description": description,
                    "status": "failed",
                    "error": error_msg,
                    "execution_time": execution_time
                })
                
                # For sequential execution, stop on first failure
                if execution_strategy == "sequential":
                    print("Sequential execution stopped due to failure")
                    break
    
    # Run the async workflow
    try:
        asyncio.run(run_workflow())
    except Exception as e:
        return f"Error running workflow: {str(e)}"
    
    # Compile final response
    successful_ops = [r for r in results if r["status"] == "success"]
    failed_ops = [r for r in results if r["status"] == "failed"]
    total_time = sum(r.get("execution_time", 0) for r in results)
    
    response = f"## AWS Cost Optimization Workflow Results\n\n"
    response += f"**Executed:** {len(results)} operations\n"
    response += f"**Successful:** {len(successful_ops)}\n"
    response += f"**Failed:** {len(failed_ops)}\n"
    response += f"**Total Execution Time:** {total_time:.2f}s\n"
    response += f"**Estimated Duration Category:** {estimated_duration}\n\n"
    
    for result in results:
        response += f"### Operation {result['sequence']}: {result['description']}\n"
        response += f"**Status:** {result['status']}\n"
        response += f"**Execution Time:** {result.get('execution_time', 0):.2f}s\n"
        
        if result["status"] == "success":
            response += f"**Result:**\n{result['result']}\n\n"
        else:
            response += f"**Error:** {result['error']}\n\n"
    
    return response


@tool
def query_cost_optimization_mcp(query: str, timeout: int = 300) -> str:
    """
    Query the remote AWS API MCP server for cost optimization information.
    
    This is a simple direct query tool for single operations that don't need
    complex preprocessing or workflow orchestration.
    
    Args:
        query: AWS CLI command or cost-related query
        timeout: Timeout in seconds for the operation
        
    Returns:
        Result from the MCP server
    """
    # Validate the query first
    validation_result = validate_prompt(query)
    
    if not validation_result["is_valid"]:
        return json.dumps({
            "error": "Query validation failed",
            "warnings": validation_result["warnings"],
            "blocked_patterns": validation_result["blocked_patterns"]
        })
    
    sanitized_query = validation_result["sanitized_input"]
    
    # Use asyncio to call the remote MCP tool
    async def execute_query():
        result = await call_remote_mcp_tool(
            tool_name="aws___run_aws_cli",
            arguments={"command": sanitized_query},
            timeout=timeout
        )
        return result
    
    try:
        result = asyncio.run(execute_query())
        
        if result["success"]:
            return result["data"]
        else:
            return json.dumps({
                "error": result.get("error", "Unknown error occurred"),
                "query": sanitized_query
            })
    except Exception as e:
        return json.dumps({
            "error": f"Exception during query execution: {str(e)}",
            "query": sanitized_query
        })


# Supervisor Agent System Prompt
SUPERVISOR_AGENT_PROMPT = """You are an AWS Cost Optimization and Billing Management Specialist Agent with intelligent prompt preprocessing capabilities and remote MCP server integration via Bedrock AgentCore Runtime.

## Your Role
Analyze incoming cost and billing queries, validate and sanitize inputs, determine their complexity, and route them through the appropriate execution path with intelligent parameter extraction and workflow coordination focused on financial optimization and cost management.

## Remote MCP Integration
You connect to a remote AWS managed API MCP server via Bedrock AgentCore Runtime. This provides:
- **AWS CLI Operations**: Execute any AWS CLI command for cost and billing services
- **Long-Running Support**: Operations can run up to 8 hours for comprehensive analysis
- **Secure Communication**: HTTPS-based communication with AWS-managed infrastructure
- **Session Management**: Automatic credential refresh and session handling

## Core Expertise Areas

### Cost Optimization
- EC2 instance rightsizing and utilization analysis
- Storage optimization (EBS, S3, EFS) and lifecycle management
- Reserved Instance and Savings Plans recommendations
- Unused and underutilized resource identification
- Cost allocation and tagging strategies

### Billing Analysis
- Cost and usage reporting across services and accounts
- Budget monitoring and variance analysis
- Cost anomaly detection and investigation
- Billing consolidation and organizational cost management
- Free Tier usage tracking and optimization

### Financial Management
- Cost forecasting and trend analysis
- Multi-account cost allocation and chargeback
- Cost center and project-based cost tracking
- ROI analysis for cloud investments
- Cost governance and policy recommendations

## Available Tools

### 1. preprocess_and_validate_prompt - Security and Complexity Analysis
Use this FIRST for any cost/billing request to:
- **Validate input security**: Prevent SQL injection, command injection, sensitive data exposure
- **Sanitize inputs**: Remove potentially malicious patterns
- **Analyze complexity**: Determine if single or multi-operation workflow
- **Extract parameters**: Identify cross-account parameters and cost dimensions
- **Estimate duration**: Classify as short/medium/long-running operation

### 2. execute_cost_optimization_workflow - Multi-Operation Orchestrator
Use this for complex cost optimization requests that need multiple operations:
- **Task restructuring**: Transform user requests into MCP-compatible operations
- **Sequential execution**: Handle operation dependencies
- **Long-running support**: Manage sessions for operations up to 8 hours
- **Comprehensive results**: Aggregate results from multiple operations

### 3. query_cost_optimization_mcp - Direct MCP Query
Use this for simple, single-operation queries:
- **Direct AWS CLI access**: Execute straightforward cost queries
- **Fast execution**: No preprocessing overhead for simple requests
- **Input validation**: Still includes security validation

### 4. think - Strategy Analysis
Use for cost optimization strategy planning that doesn't require API calls.

## Execution Flow Decision Logic

### Step 1: Always Validate First
For ANY user input, start with preprocess_and_validate_prompt to:
- Ensure input is safe and sanitized
- Analyze cost query complexity and scope
- Extract cross-account billing parameters
- Determine optimal execution strategy
- Estimate operation duration (important for long-running tasks)

### Step 2: Route Based on Complexity and Duration

#### Simple Cost Requests → query_cost_optimization_mcp
Use for:
- Single AWS CLI command
- Quick cost queries (< 5 minutes)
- No cross-service dependencies
- Complexity marked as "single"

Examples:
- "Get EC2 costs for last month"
- "List current Reserved Instances"
- "Show S3 storage costs"

#### Complex Cost Requests → execute_cost_optimization_workflow
Use for:
- Multi-service cost optimization
- Long-running analysis (> 5 minutes, up to 8 hours)
- Cross-account cost consolidation
- Sequential operation dependencies
- Complexity marked as "multi"

Examples:
- "Comprehensive cost optimization audit across all services"
- "Analyze and forecast costs for next quarter with recommendations"
- "Compare costs across all accounts with detailed breakdown"

## Long-Running Operations Support

For operations estimated as "long" duration:
- Automatically configured for up to 8 hours execution
- Session management handles credential refresh
- Progress logging at operation level
- Graceful handling of timeouts

## Security Considerations

Your input validation checks for:
- **SQL Injection**: UNION SELECT, DROP TABLE, DELETE FROM patterns
- **Command Injection**: Shell operators, command substitution
- **Sensitive Data**: AWS credentials, passwords, API keys (auto-redacted)
- **Input Length**: Maximum 10000 characters

Always sanitize inputs before passing to MCP server.

## Cost-Focused Parameter Handling

Extract and use these parameters:
- **account_id**: For cross-account cost analysis
- **role_arn**: For AssumeRole operations
- **external_id**: Enhanced security for cross-account access
- **region**: Regional cost analysis
- **time_period**: Cost analysis time ranges
- **cost_dimensions**: Service, account, region filters

## Response Guidelines

1. **Always validate first**: Never skip validation
2. **Estimate duration**: Use preprocessing to estimate operation time
3. **Choose right tool**: Direct query vs workflow based on complexity
4. **Provide context**: Include execution times and operation status
5. **Quantify impact**: Show cost savings and optimization opportunities
6. **Handle errors gracefully**: Provide actionable error messages

## Example Workflows

### Simple Query:
User: "Show Lambda costs for last month"
1. preprocess_and_validate_prompt → Validates, complexity="single", duration="short"
2. query_cost_optimization_mcp → Direct AWS CLI execution

### Complex Analysis:
User: "Complete cost optimization audit with recommendations"
1. preprocess_and_validate_prompt → Validates, complexity="multi", duration="long"
2. execute_cost_optimization_workflow → Multi-operation workflow with long-running support

### Cross-Account:
User: "Compare costs across accounts 123456789012 and 987654321098"
1. preprocess_and_validate_prompt → Extracts account_ids, complexity="multi"
2. execute_cost_optimization_workflow → Sequential operations with cross-account parameters

Your goal is to provide secure, efficient, and comprehensive cost optimization support through intelligent preprocessing, validation, and appropriate tool selection."""

# Create the supervisor agent
supervisor_agent = Agent(
    system_prompt=SUPERVISOR_AGENT_PROMPT,
    model=bedrock_model,
    tools=[
        preprocess_and_validate_prompt,
        execute_cost_optimization_workflow,
        query_cost_optimization_mcp,
        think
    ],
)


@app.entrypoint
def strands_agent_bedrock(payload):
    """
    Entrypoint for the Bedrock AgentCore Runtime.
    
    Processes incoming requests with prompt validation, task restructuring,
    and long-running operation support.
    
    Args:
        payload: Dictionary containing the user prompt and metadata
        
    Returns:
        Response text from the agent
    """
    user_input = payload.get("prompt")
    print(f"Received user input: {user_input}")
    
    # Log session information for long-running support
    session_id = payload.get("sessionId", "unknown")
    print(f"Session ID: {session_id}")
    
    # Process through supervisor agent
    response = supervisor_agent(user_input)
    
    return response.message['content'][0]['text']


# Example usage for local testing
if __name__ == "__main__":
    app.run()
