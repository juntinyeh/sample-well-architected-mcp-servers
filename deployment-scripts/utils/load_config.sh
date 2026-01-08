#!/bin/bash

# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Global configuration management for COA deployment
# This file provides common configuration loading and validation functions

# Function to load environment-specific configuration
load_environment_config() {
    local env=${1:-"prod"}
    
    # Set default values based on environment
    case "$env" in
        "dev")
            export COA_ENVIRONMENT="dev"
            export COA_LOG_LEVEL="DEBUG"
            ;;
        "staging")
            export COA_ENVIRONMENT="staging"
            export COA_LOG_LEVEL="INFO"
            ;;
        "prod")
            export COA_ENVIRONMENT="prod"
            export COA_LOG_LEVEL="WARN"
            ;;
        *)
            echo "Warning: Unknown environment '$env', using prod defaults"
            export COA_ENVIRONMENT="prod"
            export COA_LOG_LEVEL="WARN"
            ;;
    esac
}

# Function to validate AWS credentials
validate_aws_credentials() {
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        echo "Error: AWS credentials not configured or invalid"
        return 1
    fi
    return 0
}

# Function to check required tools
check_required_tools() {
    local required_tools=("aws" "python3" "pip3")
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            echo "Error: Required tool '$tool' not found"
            return 1
        fi
    done
    return 0
}

# Initialize configuration
init_config() {
    local environment=${1:-"prod"}
    
    # Load environment configuration
    load_environment_config "$environment"
    
    # Validate prerequisites
    if ! check_required_tools; then
        return 1
    fi
    
    if ! validate_aws_credentials; then
        return 1
    fi
    
    return 0
}

# Function to load deployment configuration
load_deployment_config() {
    # Load existing configuration if available
    if [[ -n "$COA_STACK_NAME" ]]; then
        echo "Loaded deployment config: stack=$COA_STACK_NAME, region=$COA_REGION, env=$COA_ENVIRONMENT"
    fi
    return 0
}

# Function to update deployment configuration
update_deployment_config() {
    local stack_name="$1"
    local region="$2"
    local environment="$3"
    
    # Create or update deployment configuration
    export COA_STACK_NAME="$stack_name"
    export COA_REGION="$region"
    export COA_ENVIRONMENT="$environment"
    
    echo "Updated deployment config: stack=$stack_name, region=$region, env=$environment"
    return 0
}

# Export functions for use in other scripts
export -f load_environment_config
export -f validate_aws_credentials
export -f check_required_tools
export -f init_config
export -f load_deployment_config
export -f update_deployment_config