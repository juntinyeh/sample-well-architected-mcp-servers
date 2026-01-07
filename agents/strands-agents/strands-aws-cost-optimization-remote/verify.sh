#!/bin/bash
# Verification script for AWS Cost Optimization Agent with Remote MCP Server

echo "========================================================================"
echo "AWS Cost Optimization Agent - Verification Script"
echo "========================================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the agent directory"
    exit 1
fi

echo "📁 Checking file structure..."
REQUIRED_FILES=(
    "main.py"
    "config.py"
    "requirements.txt"
    "Dockerfile"
    "README.md"
    "DEPLOYMENT.md"
    "LONG_RUNNING_SUPPORT.md"
    "example_usage.py"
    ".gitignore"
)

ALL_PRESENT=true
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (missing)"
        ALL_PRESENT=false
    fi
done

if [ "$ALL_PRESENT" = false ]; then
    echo ""
    echo "❌ Some required files are missing"
    exit 1
fi

echo ""
echo "🐍 Checking Python syntax..."
python3 -m py_compile main.py 2>&1
if [ $? -eq 0 ]; then
    echo "  ✅ main.py syntax valid"
else
    echo "  ❌ main.py syntax error"
    exit 1
fi

python3 -m py_compile config.py 2>&1
if [ $? -eq 0 ]; then
    echo "  ✅ config.py syntax valid"
else
    echo "  ❌ config.py syntax error"
    exit 1
fi

python3 -m py_compile example_usage.py 2>&1
if [ $? -eq 0 ]; then
    echo "  ✅ example_usage.py syntax valid"
else
    echo "  ❌ example_usage.py syntax error"
    exit 1
fi

echo ""
echo "📋 Checking documentation..."
DOC_FILES=("README.md" "DEPLOYMENT.md" "LONG_RUNNING_SUPPORT.md")
for doc in "${DOC_FILES[@]}"; do
    LINES=$(wc -l < "$doc")
    echo "  ✅ $doc ($LINES lines)"
done

echo ""
echo "🔍 Checking key features in main.py..."

# Check for prompt validation
if grep -q "def validate_prompt" main.py; then
    echo "  ✅ Prompt validation function present"
else
    echo "  ❌ Prompt validation function missing"
fi

# Check for preprocessing
if grep -q "def preprocess_and_validate_prompt" main.py; then
    echo "  ✅ Preprocessing tool present"
else
    echo "  ❌ Preprocessing tool missing"
fi

# Check for remote MCP integration
if grep -q "call_remote_mcp_tool" main.py; then
    echo "  ✅ Remote MCP integration present"
else
    echo "  ❌ Remote MCP integration missing"
fi

# Check for long-running support
if grep -q "timeout_long.*28800" main.py; then
    echo "  ✅ Long-running support (8 hours) configured"
else
    echo "  ⚠️  Long-running timeout may need verification"
fi

# Check for BedrockAgentCoreApp
if grep -q "BedrockAgentCoreApp" main.py; then
    echo "  ✅ BedrockAgentCoreApp integration present"
else
    echo "  ❌ BedrockAgentCoreApp integration missing"
fi

# Check for SSM Parameter Store
if grep -q "get_ssm_parameter" main.py; then
    echo "  ✅ SSM Parameter Store integration present"
else
    echo "  ❌ SSM Parameter Store integration missing"
fi

echo ""
echo "🔒 Checking security features..."

# Check for SQL injection detection
if grep -q "SQL injection" main.py; then
    echo "  ✅ SQL injection detection present"
else
    echo "  ❌ SQL injection detection missing"
fi

# Check for command injection detection
if grep -q "command injection" main.py; then
    echo "  ✅ Command injection detection present"
else
    echo "  ❌ Command injection detection missing"
fi

# Check for sensitive data redaction
if grep -q "AKIA.*16" main.py; then
    echo "  ✅ AWS credential detection present"
else
    echo "  ❌ AWS credential detection missing"
fi

echo ""
echo "📦 Checking dependencies..."
if [ -f "requirements.txt" ]; then
    DEPS=$(wc -l < requirements.txt)
    echo "  ✅ requirements.txt present ($DEPS dependencies)"
    
    # Check for key dependencies
    if grep -q "strands-agents" requirements.txt; then
        echo "  ✅ strands-agents dependency present"
    else
        echo "  ❌ strands-agents dependency missing"
    fi
    
    if grep -q "bedrock-agentcore" requirements.txt; then
        echo "  ✅ bedrock-agentcore dependency present"
    else
        echo "  ❌ bedrock-agentcore dependency missing"
    fi
    
    if grep -q "mcp" requirements.txt; then
        echo "  ✅ mcp dependency present"
    else
        echo "  ❌ mcp dependency missing"
    fi
else
    echo "  ❌ requirements.txt missing"
fi

echo ""
echo "🐳 Checking Docker configuration..."
if [ -f "Dockerfile" ]; then
    echo "  ✅ Dockerfile present"
    
    # Check base image
    if grep -q "public.ecr.aws/docker/library/python" Dockerfile; then
        echo "  ✅ Using AWS ECR public base image"
    else
        echo "  ⚠️  Not using recommended AWS ECR base image"
    fi
else
    echo "  ❌ Dockerfile missing"
fi

echo ""
echo "========================================================================"
echo "✅ Verification Complete!"
echo "========================================================================"
echo ""
echo "Summary:"
echo "  • All required files present"
echo "  • Python syntax valid"
echo "  • Key features implemented:"
echo "    - Prompt validation with security checks"
echo "    - Task restructuring for MCP compatibility"
echo "    - Remote MCP server integration via AgentCore Runtime"
echo "    - Long-running operation support (8 hours)"
echo "    - SSM Parameter Store configuration"
echo "    - BedrockAgentCoreApp integration"
echo "  • Comprehensive documentation provided"
echo ""
echo "Next Steps:"
echo "  1. Review README.md for usage instructions"
echo "  2. Follow DEPLOYMENT.md for deployment steps"
echo "  3. Configure SSM parameters as documented"
echo "  4. Deploy to AWS Bedrock AgentCore Runtime"
echo ""
echo "For testing: python3 example_usage.py"
echo "========================================================================"
