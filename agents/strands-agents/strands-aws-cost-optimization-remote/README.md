# AWS Cost Optimization Agent with Remote MCP Server

A sophisticated AWS cost optimization and billing management agent that connects to remote AWS managed API MCP servers via Bedrock AgentCore Runtime. This agent includes advanced features for prompt validation, task restructuring, and long-running operation support (up to 8 hours).

## Overview

This agent is an evolution of the legacy `strands-aws-cost-optimization` agent, redesigned to use remote MCP servers instead of local ones. It provides the same powerful cost optimization capabilities while leveraging AWS-managed infrastructure for improved scalability and reliability.

## Key Features

### 🔒 Security & Validation
- **Prompt Validation**: Comprehensive input validation to prevent SQL injection, command injection, and sensitive data exposure
- **Input Sanitization**: Automatic redaction of sensitive patterns (AWS credentials, API keys, passwords)
- **Pattern Detection**: Identifies and blocks potentially malicious input patterns

### 🔄 Task Restructuring
- **Intelligent Preprocessing**: Analyzes user requests to determine complexity and execution strategy
- **MCP Compatibility**: Transforms user queries into MCP-compatible tool invocations
- **Dependency Management**: Handles operation dependencies in multi-step workflows

### 🌐 Remote MCP Integration
- **Bedrock AgentCore Runtime**: Connects to AWS-managed MCP servers via HTTPS
- **SSM Parameter Store**: Retrieves connection information securely
- **Dynamic Configuration**: Supports multiple MCP server endpoints

### ⏱️ Long-Running Support
- **Extended Duration**: Supports operations up to 8 hours (as per AWS documentation)
- **Session Management**: Automatic credential refresh and session handling
- **Progress Tracking**: Detailed logging of operation progress
- **Timeout Configuration**: Intelligent timeout selection based on operation complexity

### 💰 Cost Optimization Capabilities
- **Multi-Service Analysis**: Cost analysis across all AWS services
- **Rightsizing Recommendations**: EC2 instance optimization suggestions
- **Reserved Instance Analysis**: RI and Savings Plans recommendations
- **Storage Optimization**: EBS, S3, and EFS cost optimization
- **Budget Management**: Budget monitoring and variance analysis
- **Anomaly Detection**: Cost anomaly identification and investigation

## Architecture

```
┌─────────────────────────────────────────────────┐
│  User Request                                   │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  Supervisor Agent                               │
│  - Route requests to appropriate tools          │
│  - Coordinate multi-operation workflows         │
└────────────────┬────────────────────────────────┘
                 │
     ┌───────────┼───────────┐
     │           │           │
     ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│Validate │ │Workflow │ │ Direct  │
│& Process│ │Executor │ │  Query  │
└────┬────┘ └────┬────┘ └────┬────┘
     │           │           │
     └───────────┼───────────┘
                 ▼
┌─────────────────────────────────────────────────┐
│  Remote MCP Server (via AgentCore Runtime)      │
│  - AWS API operations                           │
│  - Cost Explorer queries                        │
│  - Billing & cost management tools              │
└─────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-1` | AWS region for operations |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` | Bedrock model to use |
| `MCP_SSM_PARAMETER` | `/coa/components/aws_api_mcp/connection_info` | SSM parameter for MCP connection info |
| `TIMEOUT_SHORT` | `300` | Timeout for short operations (seconds) |
| `TIMEOUT_MEDIUM` | `1800` | Timeout for medium operations (seconds) |
| `TIMEOUT_LONG` | `28800` | Timeout for long operations (seconds) |
| `ENABLE_LONG_RUNNING` | `true` | Enable long-running operation support |
| `MAX_INPUT_LENGTH` | `10000` | Maximum input length for validation |
| `ENABLE_INPUT_VALIDATION` | `true` | Enable input validation |
| `LOG_LEVEL` | `INFO` | Logging level |

### SSM Parameter Store

The agent expects the following SSM parameter to be configured:

**Parameter Name**: `/coa/components/aws_api_mcp/connection_info`

**Format**:
```json
{
  "agent_arn": "arn:aws:bedrock:us-east-1:123456789012:agent/AGENT_ID",
  "agent_id": "AGENT_ID",
  "package_name": "awslabs.aws-api-mcp-server"
}
```

## Usage

### Installation

```bash
pip install -r requirements.txt
```

### Running the Agent

```bash
python main.py
```

### Example Queries

#### Simple Cost Query
```
Show me EC2 costs for the last month
```

#### Complex Optimization Workflow
```
Perform a comprehensive cost optimization analysis across all services, including:
- EC2 rightsizing recommendations
- Reserved Instance opportunities
- Unused EBS volumes
- S3 lifecycle optimization
```

#### Cross-Account Analysis
```
Compare costs between accounts 123456789012 and 987654321098 for the last quarter
```

## Tools Available

### 1. preprocess_and_validate_prompt
Validates and analyzes incoming user prompts.

**Input**: User query string
**Output**: Validation status, sanitized input, and complexity analysis

**Features**:
- Security validation (SQL/command injection, sensitive data)
- Complexity analysis (single vs multi-operation)
- Duration estimation (short/medium/long)
- Parameter extraction (account IDs, regions, time periods)

### 2. execute_cost_optimization_workflow
Executes multi-operation workflows with dependency management.

**Input**: Preprocessed analysis JSON
**Output**: Aggregated results from all operations

**Features**:
- Sequential/parallel execution
- Dependency resolution
- Long-running support (up to 8 hours)
- Progress tracking and logging

### 3. query_cost_optimization_mcp
Direct query tool for simple operations.

**Input**: AWS CLI command or query
**Output**: Result from MCP server

**Features**:
- Fast execution for simple queries
- Input validation
- Direct MCP server access

## Long-Running Operation Support

The agent supports long-running operations up to 8 hours, following AWS Bedrock AgentCore Runtime guidelines:

### Configuration
- **Automatic Duration Estimation**: Preprocessing step estimates operation duration
- **Timeout Selection**: Chooses appropriate timeout based on complexity
- **Session Management**: Handles credential refresh automatically

### Duration Categories
- **Short** (< 5 min): Simple queries, single service cost retrieval
- **Medium** (< 30 min): Multi-service analysis, moderate complexity
- **Long** (< 8 hours): Comprehensive audits, cross-account analysis, forecasting

### Best Practices
1. Use preprocessing to estimate duration before execution
2. Monitor operation progress through logs
3. Structure complex workflows into manageable operations
4. Handle timeouts gracefully with retry logic

## Security Considerations

### Input Validation
The agent performs comprehensive input validation to prevent:
- **SQL Injection**: UNION SELECT, DROP TABLE, DELETE FROM patterns
- **Command Injection**: Shell operators, backticks, command substitution
- **Sensitive Data Exposure**: AWS credentials, passwords, API keys

### Data Protection
- **Auto-Redaction**: Sensitive patterns automatically redacted
- **Secure Communication**: HTTPS-only communication with MCP servers
- **Credential Management**: Uses AWS SDK credential chain, no hardcoded keys

### Cross-Account Access
- Supports AssumeRole for cross-account operations
- Validates role ARNs and external IDs
- Logs all cross-account access attempts

## Performance Optimization

### Caching
- Connection info cached to reduce SSM Parameter Store calls
- MCP session pooling for improved performance

### Parallel Execution
- Optional parallel execution for independent operations
- Configurable concurrency limits

### Resource Management
- Automatic cleanup of resources after operations
- Efficient memory usage for large datasets

## Troubleshooting

### Common Issues

#### MCP Server Connection Fails
- Check SSM parameter `/coa/components/aws_api_mcp/connection_info` exists
- Verify IAM permissions for SSM Parameter Store access
- Ensure Bedrock AgentCore Runtime endpoint is accessible

#### Timeout Errors
- Check duration estimation in preprocessing output
- Adjust timeout environment variables if needed
- Consider breaking complex queries into smaller operations

#### Validation Errors
- Review validation warnings in preprocessing output
- Sanitize input to remove blocked patterns
- Disable validation temporarily for testing (not recommended for production)

## Development

### Testing
```bash
# Run with test input
python main.py --test

# Enable debug logging
export LOG_LEVEL=DEBUG
python main.py
```

### Adding New Features
1. Add new tools in `main.py`
2. Update supervisor agent prompt with new capabilities
3. Update requirements.txt if new dependencies added
4. Test with various input scenarios

## References

- [AWS Bedrock AgentCore Runtime Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Long-Running Operations Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [AWS Cost Management Best Practices](https://aws.amazon.com/aws-cost-management/best-practices/)

## License

See LICENSE file in the repository root.

## Contributing

See CONTRIBUTING.md in the repository root for contribution guidelines.
