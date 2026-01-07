"""
SSE Streaming Service for AgentCore Runtime Long-Running Invocations.

This service implements Server-Sent Events (SSE) streaming to support
long-running agent invocations with real-time response updates.

Based on AWS documentation:
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional
from enum import Enum

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class StreamEventType(Enum):
    """Types of SSE events that can be sent to the client."""
    START = "start"
    CHUNK = "chunk"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    COMPLETE = "complete"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class SSEStreamingService:
    """
    Handles SSE streaming for AgentCore Runtime long-running invocations.
    
    This service manages the invocation of AgentCore agents and streams
    responses back to the client using Server-Sent Events (SSE) protocol.
    """
    
    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the SSE Streaming Service.
        
        Args:
            region: AWS region for AgentCore client
        """
        self.region = region
        self.client = None
        self._initialize_client()
        
        logger.info(f"SSE Streaming Service initialized for region: {region}")
    
    def _initialize_client(self) -> None:
        """Initialize the boto3 AgentCore Runtime client."""
        try:
            self.client = boto3.client(
                'bedrock-agentcore-runtime',
                region_name=self.region
            )
            logger.info("AgentCore Runtime client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AgentCore Runtime client: {e}")
            raise
    
    def format_sse_event(
        self, 
        event_type: StreamEventType, 
        data: Any, 
        event_id: Optional[str] = None
    ) -> str:
        """
        Format data as an SSE event.
        
        Args:
            event_type: Type of SSE event
            data: Event data to send
            event_id: Optional event ID for tracking
            
        Returns:
            Formatted SSE event string
        """
        event_str = f"event: {event_type.value}\n"
        
        if event_id:
            event_str += f"id: {event_id}\n"
        
        # Convert data to JSON string if not already a string
        if not isinstance(data, str):
            data = json.dumps(data)
        
        event_str += f"data: {data}\n\n"
        
        return event_str
    
    async def stream_agent_response(
        self,
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        user_input: str,
        enable_trace: bool = False,
        timeout: int = 300
    ) -> AsyncGenerator[str, None]:
        """
        Stream agent response using SSE.
        
        This method invokes an AgentCore agent and streams the response
        back to the client in real-time using Server-Sent Events.
        
        Args:
            agent_id: AgentCore agent ID
            agent_alias_id: Agent alias ID
            session_id: Session ID for conversation context
            user_input: User's input message
            enable_trace: Whether to include trace information
            timeout: Maximum invocation timeout in seconds
            
        Yields:
            SSE-formatted event strings
        """
        invocation_id = f"{agent_id}_{session_id}_{datetime.utcnow().timestamp()}"
        
        try:
            # Send start event
            yield self.format_sse_event(
                StreamEventType.START,
                {
                    "invocation_id": invocation_id,
                    "agent_id": agent_id,
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                event_id=invocation_id
            )
            
            # Invoke agent with streaming
            response = await self._invoke_agent_streaming(
                agent_id=agent_id,
                agent_alias_id=agent_alias_id,
                session_id=session_id,
                user_input=user_input,
                enable_trace=enable_trace,
                timeout=timeout
            )
            
            # Stream response chunks
            async for event in self._process_response_stream(response, invocation_id):
                yield event
            
            # Send complete event
            yield self.format_sse_event(
                StreamEventType.COMPLETE,
                {
                    "invocation_id": invocation_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                event_id=invocation_id
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'UnknownError')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"AgentCore invocation error: {error_code} - {error_message}")
            
            yield self.format_sse_event(
                StreamEventType.ERROR,
                {
                    "invocation_id": invocation_id,
                    "error_code": error_code,
                    "error_message": error_message,
                    "timestamp": datetime.utcnow().isoformat()
                },
                event_id=invocation_id
            )
            
        except asyncio.TimeoutError:
            logger.error(f"AgentCore invocation timeout after {timeout}s")
            
            yield self.format_sse_event(
                StreamEventType.ERROR,
                {
                    "invocation_id": invocation_id,
                    "error_code": "TimeoutError",
                    "error_message": f"Invocation timeout after {timeout} seconds",
                    "timestamp": datetime.utcnow().isoformat()
                },
                event_id=invocation_id
            )
            
        except Exception as e:
            logger.error(f"Unexpected error during AgentCore invocation: {e}", exc_info=True)
            
            yield self.format_sse_event(
                StreamEventType.ERROR,
                {
                    "invocation_id": invocation_id,
                    "error_code": "InternalError",
                    "error_message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                },
                event_id=invocation_id
            )
    
    async def _invoke_agent_streaming(
        self,
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        user_input: str,
        enable_trace: bool = False,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Invoke AgentCore agent with streaming response.
        
        Args:
            agent_id: AgentCore agent ID
            agent_alias_id: Agent alias ID
            session_id: Session ID
            user_input: User input
            enable_trace: Include trace
            timeout: Timeout in seconds
            
        Returns:
            Streaming response object
        """
        try:
            # Invoke agent using boto3 AgentCore Runtime client
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.invoke_agent,
                    agentId=agent_id,
                    agentAliasId=agent_alias_id,
                    sessionId=session_id,
                    inputText=user_input,
                    enableTrace=enable_trace
                ),
                timeout=timeout
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to invoke agent: {e}")
            raise
    
    async def _process_response_stream(
        self, 
        response: Dict[str, Any], 
        invocation_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Process the streaming response from AgentCore.
        
        Args:
            response: Response object from invoke_agent
            invocation_id: Invocation ID for tracking
            
        Yields:
            SSE-formatted event strings
        """
        try:
            # Get the event stream from the response
            event_stream = response.get('completion', [])
            
            for event in event_stream:
                # Process different event types
                if 'chunk' in event:
                    chunk_data = event['chunk']
                    bytes_data = chunk_data.get('bytes', b'')
                    text = bytes_data.decode('utf-8') if bytes_data else ''
                    
                    if text:
                        yield self.format_sse_event(
                            StreamEventType.CHUNK,
                            {
                                "content": text,
                                "timestamp": datetime.utcnow().isoformat()
                            },
                            event_id=invocation_id
                        )
                
                elif 'trace' in event:
                    trace_data = event['trace']
                    
                    # Check if trace contains thinking or tool use
                    if 'thinking' in trace_data:
                        yield self.format_sse_event(
                            StreamEventType.THINKING,
                            {
                                "thinking": trace_data['thinking'],
                                "timestamp": datetime.utcnow().isoformat()
                            },
                            event_id=invocation_id
                        )
                    
                    if 'toolUse' in trace_data:
                        yield self.format_sse_event(
                            StreamEventType.TOOL_USE,
                            {
                                "tool_use": trace_data['toolUse'],
                                "timestamp": datetime.utcnow().isoformat()
                            },
                            event_id=invocation_id
                        )
                
                # Small delay to allow for proper streaming
                await asyncio.sleep(0.01)
            
        except Exception as e:
            logger.error(f"Error processing response stream: {e}", exc_info=True)
            raise
    
    async def send_heartbeat(self) -> str:
        """
        Generate a heartbeat event to keep the SSE connection alive.
        
        Returns:
            SSE-formatted heartbeat event
        """
        return self.format_sse_event(
            StreamEventType.HEARTBEAT,
            {"timestamp": datetime.utcnow().isoformat()}
        )
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up SSE Streaming Service")
        self.client = None
