# Comparison: Legacy vs Remote Agent

This document compares the legacy `strands-aws-cost-optimization` agent with the new `strands-aws-cost-optimization-remote` agent.

## Architecture Comparison

### Legacy Agent (strands-aws-cost-optimization)

```
User Request
    ↓
Supervisor Agent
    ↓
aws_billing_management_agent (local tool)
    ↓
Local MCP Server (stdio connection)
    ↓
awslabs.billing-cost-management-mcp-server
    ↓
AWS Cost Management APIs
```

**Connection Method:** Local stdio process
**MCP Server:** Local billing-cost-management-mcp-server
**Configuration:** Hardcoded in agent code
**Session Management:** Manual

### Remote Agent (strands-aws-cost-optimization-remote)

```
User Request
    ↓
Validation & Preprocessing
    ↓
Supervisor Agent
    ↓
Remote MCP Tool (async HTTP)
    ↓
Bedrock AgentCore Runtime Endpoint
    ↓
AWS Managed API MCP Server
    ↓
AWS Cost Management APIs (via AWS CLI)
```

**Connection Method:** HTTPS via Bedrock AgentCore Runtime
**MCP Server:** AWS managed API MCP server
**Configuration:** SSM Parameter Store
**Session Management:** Automatic (AWS managed)

## Feature Comparison

| Feature | Legacy Agent | Remote Agent | Improvement |
|---------|-------------|--------------|-------------|
| **Connection Type** | Local stdio | Remote HTTPS | ✅ More scalable |
| **MCP Server** | Local billing server | AWS managed API | ✅ AWS managed |
| **Prompt Validation** | None | Comprehensive | ✅ Security enhanced |
| **SQL Injection Protection** | No | Yes | ✅ Added |
| **Command Injection Protection** | No | Yes | ✅ Added |
| **Sensitive Data Redaction** | No | Yes | ✅ Added |
| **Task Restructuring** | Basic | Advanced | ✅ MCP optimized |
| **Long-Running Support** | No | Yes (8 hours) | ✅ Added |
| **Duration Estimation** | No | Yes (short/medium/long) | ✅ Intelligent |
| **Timeout Configuration** | Fixed | Dynamic | ✅ Adaptive |
| **Configuration Storage** | Hardcoded | SSM Parameter Store | ✅ Dynamic |
| **Session Management** | Manual | Automatic | ✅ AWS managed |
| **Progress Tracking** | Basic | Comprehensive | ✅ Enhanced |
| **Error Handling** | Basic | Advanced | ✅ Improved |
| **Documentation** | Limited | Extensive | ✅ Complete |
| **Deployment Guide** | None | Full guide | ✅ Added |
| **Security Best Practices** | Partial | Full | ✅ Complete |

## Code Structure Comparison

### Legacy Agent

```python
# main.py (~500 lines)
- Basic preprocessing with local agent
- Direct function calls to billing agent
- Limited error handling
- Hardcoded MCP server path

# aws_billing_management_agent.py
- Local MCP server via stdio
- Manual environment setup
- Limited cross-account support

# No security validation
# No long-running support
# No dynamic configuration
```

### Remote Agent

```python
# main.py (~700 lines)
- Comprehensive validation function
- Advanced preprocessing with security
- Task restructuring for MCP compatibility
- Remote MCP integration via async HTTP
- Long-running support with timeouts
- Dynamic SSM configuration
- Enhanced error handling

# config.py (~120 lines)
- Centralized configuration
- Environment variable support
- Timeout management
- Feature toggles

# Comprehensive documentation
# Security best practices
# Deployment automation
```

## Security Enhancements

### Input Validation

**Legacy:**
```python
# No validation
user_input = payload.get("prompt")
# Direct processing
```

**Remote:**
```python
# Comprehensive validation
validation_result = validate_prompt(user_input)
if not validation_result["is_valid"]:
    return error_response
sanitized_input = validation_result["sanitized_input"]
# Safe processing
```

### Pattern Detection

**Legacy:**
- ❌ No SQL injection detection
- ❌ No command injection detection
- ❌ No sensitive data redaction

**Remote:**
- ✅ SQL injection patterns blocked
- ✅ Command injection prevented
- ✅ AWS credentials auto-redacted
- ✅ Passwords and API keys sanitized

## Configuration Management

### Legacy Configuration

```python
# Hardcoded in code
MCP_SERVER_COMMAND = "awslabs.billing-cost-management-mcp-server"
WORKING_DIR = "/tmp/aws-billing-mcp/workdir"
DEFAULT_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
```

**Changes require code update and redeployment**

### Remote Configuration

```python
# Environment variables
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "...")
MCP_SSM_PARAMETER = os.getenv("MCP_SSM_PARAMETER", "/coa/...")

# SSM Parameter Store
connection_info = get_ssm_parameter("/coa/components/aws_api_mcp/connection_info")
```

**Changes via environment variables or SSM - no code update needed**

## Long-Running Operations

### Legacy Agent

```python
# No specific support
# Operations timeout based on default settings
# No duration estimation
# No adaptive timeouts
```

**Maximum effective duration:** ~15-30 minutes (default Lambda/runtime limits)

### Remote Agent

```python
# Duration estimation
"estimated_duration": "short|medium|long"

# Configurable timeouts
timeout_map = {
    "short": 300,      # 5 minutes
    "medium": 1800,    # 30 minutes
    "long": 28800      # 8 hours
}

# Automatic session management
# Progress tracking
# Graceful timeout handling
```

**Maximum supported duration:** 8 hours (as per AWS documentation)

## MCP Communication

### Legacy Agent - Local MCP

```python
# Local stdio connection
mcp_server = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(
            command="awslabs.billing-cost-management-mcp-server",
            args=[],
            env=env,
            cwd=working_dir
        )
    )
)

# Synchronous execution
with mcp_server:
    result = mcp_agent(query)
```

**Limitations:**
- Single process per invocation
- No connection pooling
- Limited scalability
- Manual lifecycle management

### Remote Agent - AWS Managed MCP

```python
# Remote HTTPS connection
encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations"

# Asynchronous execution
async with streamablehttp_client(mcp_url, headers, timeout=timedelta(seconds=timeout)) as streams:
    async with ClientSession(*streams) as session:
        await session.initialize()
        result = await session.call_tool(tool_name, arguments)
```

**Advantages:**
- AWS managed infrastructure
- Connection pooling by AWS
- Automatic scaling
- Managed lifecycle
- Enhanced reliability

## Error Handling

### Legacy Agent

```python
try:
    result = preprocessing_agent(query)
except Exception as e:
    # Basic fallback
    return simple_analysis
```

### Remote Agent

```python
try:
    result = await call_remote_mcp_tool(...)
except TimeoutError:
    return {
        "success": False,
        "error": "Operation timeout",
        "retry_suggested": True
    }
except ConnectionError:
    return {
        "success": False,
        "error": "MCP server connection failed",
        "check": ["SSM parameters", "IAM permissions"]
    }
except Exception as e:
    return {
        "success": False,
        "error": str(e),
        "context": operation_context
    }
```

## Documentation

### Legacy Agent

- Basic README
- Limited usage examples
- No deployment guide
- No troubleshooting section

**Total documentation:** ~100 lines

### Remote Agent

- Comprehensive README (278 lines)
- Detailed deployment guide (508 lines)
- Long-running support guide (385 lines)
- Implementation summary
- Usage examples with tests
- Security documentation

**Total documentation:** ~1500+ lines

## Testing

### Legacy Agent

```python
# Basic example usage
if __name__ == "__main__":
    result = aws_billing_management_agent("query")
    print(result)
```

### Remote Agent

```python
# Comprehensive testing
- Validation tests (SQL/command injection)
- Preprocessing tests (complexity analysis)
- Duration estimation tests
- Security feature demos
- Long-running operation scenarios
- Error handling verification
```

## Deployment

### Legacy Agent Deployment

1. Copy code to runtime
2. Install local MCP server
3. Configure environment
4. Deploy

**Complexity:** Medium
**Time:** ~30 minutes
**Documentation:** Minimal

### Remote Agent Deployment

1. Configure SSM parameters
2. Create IAM role with policies
3. Build and package agent
4. Deploy to Bedrock AgentCore
5. Configure environment variables
6. Test deployment
7. Set up monitoring

**Complexity:** Higher initial setup
**Time:** ~1-2 hours (first time)
**Documentation:** Complete step-by-step guide
**Benefit:** More robust and maintainable

## Performance

### Legacy Agent

**Startup Time:** 2-5 seconds (local MCP server initialization)
**Operation Latency:** Low (local communication)
**Concurrent Requests:** Limited (single process)
**Scalability:** Manual scaling required

### Remote Agent

**Startup Time:** < 1 second (no local server)
**Operation Latency:** Slightly higher (HTTPS)
**Concurrent Requests:** High (AWS managed)
**Scalability:** Automatic (AWS infrastructure)

## Cost Considerations

### Legacy Agent

**Costs:**
- Compute time for agent
- Compute time for local MCP server
- Memory for both processes

### Remote Agent

**Costs:**
- Compute time for agent only
- AWS managed MCP server (included)
- Bedrock AgentCore Runtime fees
- SSM Parameter Store (minimal)

**Note:** Remote agent may be more cost-effective at scale due to AWS optimization

## Maintenance

### Legacy Agent

- Manual updates to local MCP server
- Code changes require full redeployment
- Limited monitoring capabilities
- Manual scaling adjustments

### Remote Agent

- MCP server managed by AWS
- Configuration changes via SSM (no redeployment)
- Comprehensive CloudWatch integration
- Automatic scaling by AWS

## Migration Path

### Migrating from Legacy to Remote

1. **Phase 1: Setup**
   - Deploy AWS API MCP server
   - Configure SSM parameters
   - Set up IAM roles

2. **Phase 2: Testing**
   - Deploy remote agent in parallel
   - Test with sample queries
   - Compare results with legacy agent

3. **Phase 3: Validation**
   - Verify long-running operations
   - Test security features
   - Validate error handling

4. **Phase 4: Cutover**
   - Route production traffic to remote agent
   - Monitor performance and errors
   - Keep legacy agent as backup

5. **Phase 5: Decommission**
   - Remove legacy agent once stable
   - Clean up old resources

**Estimated Migration Time:** 1-2 weeks

## Recommendations

### Use Remote Agent When:

✅ **Scalability is important**
- Need to handle many concurrent requests
- Want AWS-managed infrastructure

✅ **Security is critical**
- Need input validation and sanitization
- Require comprehensive audit logging

✅ **Long-running operations needed**
- Operations take more than 30 minutes
- Need comprehensive analysis workflows

✅ **Dynamic configuration required**
- Want to change settings without redeployment
- Need environment-specific configurations

### Keep Legacy Agent When:

⚠️ **Simplicity is preferred**
- Simple, single-service cost queries only
- Don't need advanced features

⚠️ **Local control required**
- Need full control over MCP server
- Have specific local MCP server requirements

⚠️ **Migration not feasible**
- Limited time for migration
- Existing integrations difficult to change

## Conclusion

The remote agent provides significant improvements over the legacy agent:

### Key Advantages
1. **Security:** Comprehensive input validation and sanitization
2. **Scalability:** AWS-managed infrastructure with auto-scaling
3. **Reliability:** Automatic session management and error handling
4. **Flexibility:** Dynamic configuration via SSM Parameter Store
5. **Long-Running:** Support for operations up to 8 hours
6. **Documentation:** Extensive guides and examples

### Trade-offs
1. **Complexity:** More sophisticated setup and configuration
2. **Latency:** Slightly higher due to HTTPS communication
3. **Dependencies:** Requires AWS managed services (SSM, Bedrock AgentCore)

### Overall Assessment

**The remote agent is recommended for production deployments** due to:
- Enhanced security features
- Better scalability and reliability
- AWS-managed infrastructure benefits
- Comprehensive long-running support
- Future-proof architecture

The initial setup complexity is offset by reduced maintenance and improved capabilities.

---

**Document Version:** 1.0
**Date:** 2025-01-07
**Status:** Complete
