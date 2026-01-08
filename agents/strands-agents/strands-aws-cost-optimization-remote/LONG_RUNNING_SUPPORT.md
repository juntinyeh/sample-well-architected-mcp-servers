# Long-Running Operation Support

This document describes the long-running operation support in the AWS Cost Optimization Agent, which enables operations to run for extended periods (up to 8 hours) as documented in the AWS Bedrock AgentCore Runtime documentation.

## Overview

The agent implements long-running support following AWS Bedrock AgentCore Runtime best practices as described at:
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html

This enables complex cost optimization workflows such as:
- Comprehensive multi-account cost audits
- Historical trend analysis with forecasting
- Large-scale resource optimization recommendations
- Cross-regional cost comparison and analysis

## Architecture

### Duration Estimation

The agent automatically estimates operation duration during preprocessing:

```python
"estimated_duration": "short|medium|long"
```

**Duration Categories:**
- **Short** (< 5 minutes): Single service queries, quick cost retrieval
- **Medium** (< 30 minutes): Multi-service analysis, moderate complexity
- **Long** (< 8 hours): Comprehensive audits, forecasting, cross-account analysis

### Timeout Configuration

Timeouts are automatically selected based on duration estimation:

| Duration | Default Timeout | Environment Variable |
|----------|----------------|---------------------|
| Short    | 300s (5 min)   | `TIMEOUT_SHORT`     |
| Medium   | 1800s (30 min) | `TIMEOUT_MEDIUM`    |
| Long     | 28800s (8 hrs) | `TIMEOUT_LONG`      |

## Implementation Details

### 1. Preprocessing Phase

The `preprocess_and_validate_prompt` tool analyzes the request and estimates duration:

```python
{
    "analysis": {
        "complexity": "multi",
        "estimated_duration": "long",
        "reasoning": "Comprehensive analysis across multiple services"
    }
}
```

### 2. Workflow Execution

The `execute_cost_optimization_workflow` tool uses the duration estimate:

```python
# Configure timeout based on estimated duration
timeout_map = {
    "short": 300,
    "medium": 1800,
    "long": 28800
}
operation_timeout = timeout_map.get(estimated_duration, 1800)
```

### 3. MCP Communication

The remote MCP tool call supports configurable timeouts:

```python
async with streamablehttp_client(
    mcp_url,
    mcp_headers,
    timeout=timedelta(seconds=timeout)
) as (read_stream, write_stream, _):
    # Operation executes with specified timeout
```

### 4. Session Management

AWS Bedrock AgentCore Runtime handles:
- Automatic credential refresh
- Session maintenance during long operations
- Connection keep-alive
- Graceful timeout handling

## Usage Examples

### Example 1: Quick Cost Query (Short Duration)

**Query:**
```
Show me Lambda costs for last month
```

**Preprocessing Output:**
```json
{
    "analysis": {
        "complexity": "single",
        "estimated_duration": "short"
    }
}
```

**Execution:**
- Timeout: 5 minutes
- Tool: `query_cost_optimization_mcp` (direct query)
- Expected completion: < 1 minute

### Example 2: Multi-Service Analysis (Medium Duration)

**Query:**
```
Analyze costs for EC2, S3, and RDS over the last quarter with month-over-month comparison
```

**Preprocessing Output:**
```json
{
    "analysis": {
        "complexity": "multi",
        "estimated_duration": "medium",
        "detected_services": ["ec2", "s3", "rds"]
    },
    "operations": [
        {"sequence": 1, "description": "Get EC2 costs"},
        {"sequence": 2, "description": "Get S3 costs"},
        {"sequence": 3, "description": "Get RDS costs"},
        {"sequence": 4, "description": "Compare trends"}
    ]
}
```

**Execution:**
- Timeout: 30 minutes
- Tool: `execute_cost_optimization_workflow`
- Expected completion: 5-15 minutes

### Example 3: Comprehensive Audit (Long Duration)

**Query:**
```
Perform a complete cost optimization audit across all AWS accounts in my organization, including:
- Historical cost analysis for the past 12 months
- Trend analysis and forecasting for next quarter
- Rightsizing recommendations for all compute resources
- Reserved Instance and Savings Plans opportunities
- Storage optimization across all storage services
- Unused and underutilized resource identification
```

**Preprocessing Output:**
```json
{
    "analysis": {
        "complexity": "multi",
        "estimated_duration": "long",
        "detected_services": ["ec2", "rds", "s3", "ebs", "efs", "lambda", "fargate"],
        "cost_focus_areas": ["rightsizing", "reserved_instances", "storage_optimization"]
    },
    "operations": [
        {"sequence": 1, "description": "Historical cost retrieval (12 months)"},
        {"sequence": 2, "description": "Trend analysis and forecasting"},
        {"sequence": 3, "description": "EC2 rightsizing analysis"},
        {"sequence": 4, "description": "RDS rightsizing analysis"},
        {"sequence": 5, "description": "Reserved Instance recommendations"},
        {"sequence": 6, "description": "Savings Plans opportunities"},
        {"sequence": 7, "description": "S3 lifecycle optimization"},
        {"sequence": 8, "description": "EBS volume optimization"},
        {"sequence": 9, "description": "Unused resource identification"},
        {"sequence": 10, "description": "Compile comprehensive report"}
    ]
}
```

**Execution:**
- Timeout: 8 hours
- Tool: `execute_cost_optimization_workflow`
- Expected completion: 2-6 hours (depending on organization size)

## Best Practices

### 1. Structure Large Workloads

For very large analyses, structure operations efficiently:

**Good:**
```
- Operation 1: Analyze compute costs (EC2, Lambda, Fargate)
- Operation 2: Analyze storage costs (S3, EBS, EFS)
- Operation 3: Analyze database costs (RDS, DynamoDB, Redshift)
- Operation 4: Compile recommendations
```

**Avoid:**
```
- Operation 1: Get every single EC2 instance detail across all accounts
  (Too granular, may not need all details for cost analysis)
```

### 2. Use Progressive Refinement

Start broad, then drill down:

```
1. Get organization-wide cost overview (fast)
2. Identify top spending services (fast)
3. Deep dive into top 3 services (medium)
4. Generate detailed recommendations (medium)
```

### 3. Monitor Progress

Enable detailed logging to track progress:

```python
# In workflow execution
print(f"Operation {sequence}/{total_operations}: {description}")
print(f"Progress: {(sequence/total_operations)*100:.1f}%")
```

### 4. Handle Timeouts Gracefully

Implement retry logic for critical operations:

```python
try:
    result = await call_remote_mcp_tool(...)
except TimeoutError:
    # Retry with smaller scope or extended timeout
    pass
```

### 5. Session State Management

For multi-hour operations:
- Store intermediate results
- Enable resume capability for critical workflows
- Log state transitions

## Configuration

### Environment Variables

```bash
# Enable long-running support
export ENABLE_LONG_RUNNING=true

# Set maximum operation duration (in seconds)
export MAX_OPERATION_DURATION=28800  # 8 hours

# Configure timeouts for each duration category
export TIMEOUT_SHORT=300      # 5 minutes
export TIMEOUT_MEDIUM=1800    # 30 minutes
export TIMEOUT_LONG=28800     # 8 hours

# Enable detailed logging for long operations
export LOG_LEVEL=INFO
```

### IAM Permissions

Ensure the agent's IAM role has permissions for:
- AWS Cost Explorer API (all read operations)
- Bedrock AgentCore Runtime (long session support)
- CloudWatch Logs (for progress logging)
- SSM Parameter Store (for configuration)

## Monitoring

### CloudWatch Logs

Monitor operation progress:
```
[INFO] Starting cost optimization workflow
[INFO] Operation 1/10: Historical cost retrieval
[INFO] ✅ Operation 1 completed in 45.3s
[INFO] Operation 2/10: Trend analysis
[INFO] ✅ Operation 2 completed in 120.7s
...
[INFO] ✅ All operations completed. Total time: 3247.5s
```

### CloudWatch Metrics

Custom metrics to track:
- Operation duration by category (short/medium/long)
- Success/failure rates
- Timeout occurrences
- Average execution time per operation type

## Troubleshooting

### Operation Times Out

**Symptoms:**
- Operation exceeds configured timeout
- No results returned after long wait

**Solutions:**
1. Increase timeout for the duration category
2. Break operation into smaller chunks
3. Check MCP server availability
4. Review AWS service quotas

### Slow Performance

**Symptoms:**
- Operations take longer than expected
- Progressive slowdown during workflow

**Solutions:**
1. Check AWS service API throttling
2. Reduce concurrent operations
3. Optimize query scope (filter by region, service)
4. Use caching for repeated queries

### Session Expiration

**Symptoms:**
- "Session expired" errors during long operations
- Authentication failures mid-workflow

**Solutions:**
1. Ensure IAM role has proper trust policy
2. Verify Bedrock AgentCore Runtime session settings
3. Check credential refresh configuration
4. Monitor CloudWatch logs for credential events

## Performance Optimization

### 1. Parallel Execution (Future Enhancement)

For independent operations, enable parallel execution:

```python
# In config.py
enable_parallel_execution = True
max_concurrent_operations = 5
```

### 2. Query Optimization

Optimize AWS API calls:
- Use appropriate time granularity (daily vs monthly)
- Filter by specific resources when possible
- Leverage Cost Explorer's grouping features

### 3. Caching

Implement caching for repeated queries:
- Connection info from SSM Parameter Store
- Service metadata
- Static reference data

## References

- [AWS Bedrock AgentCore Runtime Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Long-Running Operations Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html)
- [AWS Cost Explorer API Reference](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/)
- [Bedrock Runtime Lifecycle](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-sessions.html)

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-XX | Initial long-running support implementation |
| | | - Duration estimation in preprocessing |
| | | - Configurable timeouts (short/medium/long) |
| | | - Session management integration |
| | | - Progress tracking and logging |

## Future Enhancements

1. **Checkpoint/Resume**: Save state for very long operations to resume after interruption
2. **Parallel Execution**: Execute independent operations concurrently
3. **Adaptive Timeout**: Dynamically adjust timeout based on actual performance
4. **Cost Prediction**: Predict operation cost before execution
5. **Progress Callbacks**: Real-time progress updates to client
