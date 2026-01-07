"""
Configuration module for AWS Cost Optimization Agent with Remote MCP Server

This module provides configuration management for the agent, including:
- AWS region settings
- MCP server connection parameters
- Long-running operation settings
- Timeout configurations
"""

import os
from typing import Dict, Any, Optional


class AgentConfig:
    """Configuration class for the Cost Optimization Agent"""
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.bedrock_model_id = os.getenv(
            "BEDROCK_MODEL_ID",
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        )
        
        # MCP Server Configuration
        self.mcp_ssm_parameter = os.getenv(
            "MCP_SSM_PARAMETER",
            "/coa/components/aws_api_mcp/connection_info"
        )
        
        # Timeout Configuration (in seconds)
        self.timeout_short = int(os.getenv("TIMEOUT_SHORT", "300"))      # 5 minutes
        self.timeout_medium = int(os.getenv("TIMEOUT_MEDIUM", "1800"))   # 30 minutes
        self.timeout_long = int(os.getenv("TIMEOUT_LONG", "28800"))      # 8 hours
        
        # Long-Running Operation Settings
        self.enable_long_running = os.getenv("ENABLE_LONG_RUNNING", "true").lower() == "true"
        self.max_operation_duration = int(os.getenv("MAX_OPERATION_DURATION", "28800"))  # 8 hours
        
        # Validation Settings
        self.max_input_length = int(os.getenv("MAX_INPUT_LENGTH", "10000"))
        self.enable_input_validation = os.getenv("ENABLE_INPUT_VALIDATION", "true").lower() == "true"
        
        # Logging Settings
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_group_name = os.getenv("BEDROCK_LOG_GROUP_NAME", "/aws/bedrock/agentcore")
        
        # Performance Settings
        self.enable_parallel_execution = os.getenv("ENABLE_PARALLEL_EXECUTION", "false").lower() == "true"
        self.max_concurrent_operations = int(os.getenv("MAX_CONCURRENT_OPERATIONS", "5"))
    
    def get_timeout_for_duration(self, duration: str) -> int:
        """
        Get timeout value based on duration category.
        
        Args:
            duration: Duration category ("short", "medium", or "long")
            
        Returns:
            Timeout value in seconds
        """
        timeout_map = {
            "short": self.timeout_short,
            "medium": self.timeout_medium,
            "long": self.timeout_long
        }
        return timeout_map.get(duration, self.timeout_medium)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            "aws_region": self.aws_region,
            "bedrock_model_id": self.bedrock_model_id,
            "mcp_ssm_parameter": self.mcp_ssm_parameter,
            "timeout_short": self.timeout_short,
            "timeout_medium": self.timeout_medium,
            "timeout_long": self.timeout_long,
            "enable_long_running": self.enable_long_running,
            "max_operation_duration": self.max_operation_duration,
            "max_input_length": self.max_input_length,
            "enable_input_validation": self.enable_input_validation,
            "log_level": self.log_level,
            "log_group_name": self.log_group_name,
            "enable_parallel_execution": self.enable_parallel_execution,
            "max_concurrent_operations": self.max_concurrent_operations
        }
    
    def __repr__(self) -> str:
        """String representation of configuration"""
        return f"AgentConfig(region={self.aws_region}, model={self.bedrock_model_id})"


# Global configuration instance
config = AgentConfig()


def get_config() -> AgentConfig:
    """
    Get the global configuration instance.
    
    Returns:
        AgentConfig instance
    """
    return config


def reload_config() -> AgentConfig:
    """
    Reload configuration from environment variables.
    
    Returns:
        New AgentConfig instance
    """
    global config
    config = AgentConfig()
    return config
