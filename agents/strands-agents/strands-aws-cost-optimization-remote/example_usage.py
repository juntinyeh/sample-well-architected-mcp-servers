"""
Example usage and testing for AWS Cost Optimization Agent with Remote MCP Server

This script demonstrates various use cases and testing scenarios for the agent.
"""

import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    validate_prompt,
    preprocess_and_validate_prompt,
    execute_cost_optimization_workflow,
    query_cost_optimization_mcp,
    supervisor_agent
)


def test_prompt_validation():
    """Test prompt validation functionality"""
    print("=" * 80)
    print("TEST: Prompt Validation")
    print("=" * 80)
    
    # Test 1: Valid input
    print("\n1. Valid Input:")
    result = validate_prompt("Show me EC2 costs for the last month")
    print(f"  Valid: {result['is_valid']}")
    print(f"  Warnings: {result['warnings']}")
    
    # Test 2: SQL injection attempt
    print("\n2. SQL Injection Attempt:")
    result = validate_prompt("Show costs WHERE 1=1 OR DROP TABLE users")
    print(f"  Valid: {result['is_valid']}")
    print(f"  Warnings: {result['warnings']}")
    print(f"  Blocked patterns: {result['blocked_patterns']}")
    
    # Test 3: Command injection attempt
    print("\n3. Command Injection Attempt:")
    result = validate_prompt("Get costs; rm -rf /")
    print(f"  Valid: {result['is_valid']}")
    print(f"  Warnings: {result['warnings']}")
    
    # Test 4: Sensitive data detection
    print("\n4. Sensitive Data Detection:")
    result = validate_prompt("Use API key AKIAIOSFODNN7EXAMPLE to get costs")
    print(f"  Valid: {result['is_valid']}")
    print(f"  Warnings: {result['warnings']}")
    print(f"  Sanitized: {result['sanitized_input']}")
    
    # Test 5: Empty input
    print("\n5. Empty Input:")
    result = validate_prompt("")
    print(f"  Valid: {result['is_valid']}")
    print(f"  Warnings: {result['warnings']}")
    
    print("\n" + "=" * 80)


def test_preprocessing():
    """Test preprocessing and complexity analysis"""
    print("=" * 80)
    print("TEST: Preprocessing and Complexity Analysis")
    print("=" * 80)
    
    test_queries = [
        {
            "name": "Simple Query",
            "query": "Show me EC2 costs for the last month"
        },
        {
            "name": "Complex Multi-Service Analysis",
            "query": "Perform a comprehensive cost optimization analysis including EC2 rightsizing, Reserved Instance recommendations, unused EBS volumes, and S3 lifecycle optimization"
        },
        {
            "name": "Cross-Account Comparison",
            "query": "Compare costs between accounts 123456789012 and 987654321098 for the last quarter"
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n{i}. {test['name']}:")
        print(f"   Query: {test['query']}")
        
        try:
            result_str = preprocess_and_validate_prompt.fn(test['query'])
            result = json.loads(result_str)
            
            print(f"   Validation: {'✅ Valid' if result.get('validation', {}).get('is_valid') else '❌ Invalid'}")
            
            analysis = result.get('analysis', {})
            if analysis:
                print(f"   Complexity: {analysis.get('complexity', 'unknown')}")
                print(f"   Duration: {analysis.get('estimated_duration', 'unknown')}")
                print(f"   Services: {', '.join(analysis.get('detected_services', []))}")
                print(f"   Operations: {len(result.get('operations', []))}")
        except Exception as e:
            print(f"   Error: {str(e)}")
    
    print("\n" + "=" * 80)


def test_supervisor_agent():
    """Test supervisor agent with various queries"""
    print("=" * 80)
    print("TEST: Supervisor Agent")
    print("=" * 80)
    
    test_queries = [
        "Show me a summary of Lambda costs for the last 3 months",
        "What are my total AWS costs this year?",
        "Identify cost optimization opportunities for EC2 instances"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: {query}")
        print("   " + "-" * 70)
        
        try:
            # Note: This would actually invoke the agent, which requires proper setup
            print("   [Simulation mode - agent would be invoked in production]")
            print("   Expected flow:")
            print("   1. Validate and preprocess input")
            print("   2. Determine complexity and duration")
            print("   3. Route to appropriate tool (direct query or workflow)")
            print("   4. Return comprehensive results")
        except Exception as e:
            print(f"   Error: {str(e)}")
    
    print("\n" + "=" * 80)


def demo_long_running_support():
    """Demonstrate long-running operation configuration"""
    print("=" * 80)
    print("DEMO: Long-Running Operation Support")
    print("=" * 80)
    
    scenarios = [
        {
            "name": "Quick Cost Query",
            "duration": "short",
            "timeout": 300,
            "description": "Single service cost retrieval"
        },
        {
            "name": "Multi-Service Analysis",
            "duration": "medium",
            "timeout": 1800,
            "description": "Cost analysis across 3-5 services"
        },
        {
            "name": "Comprehensive Audit",
            "duration": "long",
            "timeout": 28800,
            "description": "Full organization cost optimization audit"
        }
    ]
    
    print("\nDuration Categories and Configuration:")
    for scenario in scenarios:
        print(f"\n📊 {scenario['name']}")
        print(f"   Duration Category: {scenario['duration']}")
        print(f"   Timeout: {scenario['timeout']}s ({scenario['timeout'] // 3600}h {(scenario['timeout'] % 3600) // 60}m)")
        print(f"   Description: {scenario['description']}")
        print(f"   Use Case: Operations that typically complete within this timeframe")
    
    print("\n\n🔧 Configuration:")
    print("   Environment variables for customization:")
    print("   - TIMEOUT_SHORT: Override short operation timeout")
    print("   - TIMEOUT_MEDIUM: Override medium operation timeout")
    print("   - TIMEOUT_LONG: Override long operation timeout (max 8 hours)")
    print("   - ENABLE_LONG_RUNNING: Enable/disable long-running support")
    
    print("\n\n📝 Best Practices:")
    print("   1. Always preprocess to estimate duration")
    print("   2. Break very long operations into smaller chunks when possible")
    print("   3. Monitor logs for progress tracking")
    print("   4. Implement graceful timeout handling")
    print("   5. Use session management for credential refresh")
    
    print("\n" + "=" * 80)


def demo_security_features():
    """Demonstrate security features"""
    print("=" * 80)
    print("DEMO: Security Features")
    print("=" * 80)
    
    print("\n🔒 Input Validation:")
    print("   - SQL Injection Detection")
    print("   - Command Injection Prevention")
    print("   - Sensitive Data Redaction")
    print("   - Input Length Validation")
    
    print("\n🛡️ Sensitive Pattern Detection:")
    patterns = [
        ("AWS Access Keys", r"AKIA[0-9A-Z]{16}"),
        ("Secret Keys", r"aws_secret_access_key\s*="),
        ("Passwords", r"password\s*=\s*['\"]"),
        ("API Keys", r"api[_-]?key\s*=\s*['\"]")
    ]
    
    for name, pattern in patterns:
        print(f"   - {name}: {pattern}")
    
    print("\n🔐 Secure Communication:")
    print("   - HTTPS-only MCP server communication")
    print("   - AWS SDK credential chain (no hardcoded keys)")
    print("   - IAM role-based access control")
    print("   - SSM Parameter Store for sensitive configuration")
    
    print("\n✅ Compliance:")
    print("   - No sensitive data in logs")
    print("   - Audit trail via CloudWatch Logs")
    print("   - Encryption in transit (TLS)")
    print("   - Least privilege IAM policies")
    
    print("\n" + "=" * 80)


def main():
    """Run all tests and demos"""
    print("\n" + "=" * 80)
    print("AWS Cost Optimization Agent - Examples and Tests")
    print("=" * 80)
    
    # Run tests
    test_prompt_validation()
    print("\n")
    
    test_preprocessing()
    print("\n")
    
    test_supervisor_agent()
    print("\n")
    
    # Run demos
    demo_long_running_support()
    print("\n")
    
    demo_security_features()
    print("\n")
    
    print("=" * 80)
    print("All tests and demos completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
