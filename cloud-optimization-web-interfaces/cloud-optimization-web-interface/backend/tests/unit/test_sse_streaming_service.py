"""
Unit tests for SSE Streaming Service.
"""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from agentcore.services.sse_streaming_service import (
    SSEStreamingService,
    StreamEventType
)


class TestSSEStreamingService:
    """Test suite for SSE Streaming Service."""
    
    @pytest.fixture
    def mock_boto3_client(self):
        """Create a mock boto3 client."""
        with patch('boto3.client') as mock_client:
            mock_agentcore_client = Mock()
            mock_client.return_value = mock_agentcore_client
            yield mock_agentcore_client
    
    @pytest.fixture
    def sse_service(self, mock_boto3_client):
        """Create an SSE streaming service instance."""
        return SSEStreamingService(region="us-east-1")
    
    def test_initialization(self, sse_service):
        """Test service initialization."""
        assert sse_service.region == "us-east-1"
        assert sse_service.client is not None
    
    def test_format_sse_event_basic(self, sse_service):
        """Test basic SSE event formatting."""
        event = sse_service.format_sse_event(
            StreamEventType.CHUNK,
            {"content": "test message"}
        )
        
        assert "event: chunk\n" in event
        assert "data: " in event
        assert "test message" in event
        assert event.endswith("\n\n")
    
    def test_format_sse_event_with_id(self, sse_service):
        """Test SSE event formatting with event ID."""
        event = sse_service.format_sse_event(
            StreamEventType.START,
            {"message": "starting"},
            event_id="test-123"
        )
        
        assert "event: start\n" in event
        assert "id: test-123\n" in event
        assert "data: " in event
    
    def test_format_sse_event_with_dict_data(self, sse_service):
        """Test SSE event formatting with dictionary data."""
        data = {
            "status": "processing",
            "progress": 50,
            "timestamp": "2024-01-01T00:00:00"
        }
        
        event = sse_service.format_sse_event(
            StreamEventType.THINKING,
            data
        )
        
        assert "event: thinking\n" in event
        # Data should be JSON-encoded
        assert '"status": "processing"' in event or '"status":"processing"' in event
    
    def test_format_sse_event_with_string_data(self, sse_service):
        """Test SSE event formatting with string data."""
        event = sse_service.format_sse_event(
            StreamEventType.CHUNK,
            "plain text message"
        )
        
        assert "data: plain text message\n\n" in event
    
    @pytest.mark.asyncio
    async def test_stream_agent_response_start_event(self, sse_service, mock_boto3_client):
        """Test that stream_agent_response sends start event."""
        # Mock the invoke_agent response
        mock_boto3_client.invoke_agent.return_value = {
            'completion': []
        }
        
        events = []
        async for event in sse_service.stream_agent_response(
            agent_id="test-agent",
            agent_alias_id="test-alias",
            session_id="test-session",
            user_input="test input"
        ):
            events.append(event)
        
        # First event should be START
        assert len(events) > 0
        start_event = events[0]
        assert "event: start\n" in start_event
        assert "test-agent" in start_event
    
    @pytest.mark.asyncio
    async def test_stream_agent_response_complete_event(self, sse_service, mock_boto3_client):
        """Test that stream_agent_response sends complete event."""
        mock_boto3_client.invoke_agent.return_value = {
            'completion': []
        }
        
        events = []
        async for event in sse_service.stream_agent_response(
            agent_id="test-agent",
            agent_alias_id="test-alias",
            session_id="test-session",
            user_input="test input"
        ):
            events.append(event)
        
        # Last event should be COMPLETE
        assert len(events) > 0
        complete_event = events[-1]
        assert "event: complete\n" in complete_event
    
    @pytest.mark.asyncio
    async def test_stream_agent_response_with_chunks(self, sse_service, mock_boto3_client):
        """Test streaming with chunk events."""
        # Mock streaming response with chunks
        mock_boto3_client.invoke_agent.return_value = {
            'completion': [
                {'chunk': {'bytes': b'Hello '}},
                {'chunk': {'bytes': b'World'}},
                {'chunk': {'bytes': b'!'}}
            ]
        }
        
        events = []
        async for event in sse_service.stream_agent_response(
            agent_id="test-agent",
            agent_alias_id="test-alias",
            session_id="test-session",
            user_input="test input"
        ):
            events.append(event)
        
        # Should have start, chunks, and complete events
        assert len(events) >= 5  # start + 3 chunks + complete
        
        # Check for chunk events
        chunk_events = [e for e in events if "event: chunk\n" in e]
        assert len(chunk_events) == 3
        assert "Hello" in chunk_events[0]
        assert "World" in chunk_events[1]
    
    @pytest.mark.asyncio
    async def test_stream_agent_response_with_trace(self, sse_service, mock_boto3_client):
        """Test streaming with trace events."""
        mock_boto3_client.invoke_agent.return_value = {
            'completion': [
                {'trace': {'thinking': 'Analyzing the question...'}},
                {'trace': {'toolUse': {'name': 'calculator', 'input': '2+2'}}}
            ]
        }
        
        events = []
        async for event in sse_service.stream_agent_response(
            agent_id="test-agent",
            agent_alias_id="test-alias",
            session_id="test-session",
            user_input="test input",
            enable_trace=True
        ):
            events.append(event)
        
        # Check for thinking event
        thinking_events = [e for e in events if "event: thinking\n" in e]
        assert len(thinking_events) == 1
        assert "Analyzing" in thinking_events[0]
        
        # Check for tool_use event
        tool_use_events = [e for e in events if "event: tool_use\n" in e]
        assert len(tool_use_events) == 1
        assert "calculator" in tool_use_events[0]
    
    @pytest.mark.asyncio
    async def test_stream_agent_response_client_error(self, sse_service, mock_boto3_client):
        """Test error handling for ClientError."""
        from botocore.exceptions import ClientError
        
        error_response = {
            'Error': {
                'Code': 'ResourceNotFoundException',
                'Message': 'Agent not found'
            }
        }
        mock_boto3_client.invoke_agent.side_effect = ClientError(
            error_response, 
            'InvokeAgent'
        )
        
        events = []
        async for event in sse_service.stream_agent_response(
            agent_id="nonexistent-agent",
            agent_alias_id="test-alias",
            session_id="test-session",
            user_input="test input"
        ):
            events.append(event)
        
        # Should have start and error events
        assert len(events) >= 2
        
        # Last event should be ERROR
        error_event = events[-1]
        assert "event: error\n" in error_event
        assert "ResourceNotFoundException" in error_event
        assert "Agent not found" in error_event
    
    @pytest.mark.asyncio
    async def test_stream_agent_response_timeout(self, sse_service, mock_boto3_client):
        """Test timeout handling."""
        # Simulate timeout
        async def slow_invoke(*args, **kwargs):
            await asyncio.sleep(10)
            return {'completion': []}
        
        mock_boto3_client.invoke_agent.side_effect = slow_invoke
        
        events = []
        async for event in sse_service.stream_agent_response(
            agent_id="test-agent",
            agent_alias_id="test-alias",
            session_id="test-session",
            user_input="test input",
            timeout=1  # Short timeout
        ):
            events.append(event)
        
        # Should have start and error events
        error_event = events[-1]
        assert "event: error\n" in error_event
        assert "TimeoutError" in error_event
    
    @pytest.mark.asyncio
    async def test_stream_agent_response_unexpected_error(self, sse_service, mock_boto3_client):
        """Test handling of unexpected errors."""
        mock_boto3_client.invoke_agent.side_effect = Exception("Unexpected error")
        
        events = []
        async for event in sse_service.stream_agent_response(
            agent_id="test-agent",
            agent_alias_id="test-alias",
            session_id="test-session",
            user_input="test input"
        ):
            events.append(event)
        
        # Should have error event
        error_event = events[-1]
        assert "event: error\n" in error_event
        assert "InternalError" in error_event
        assert "Unexpected error" in error_event
    
    @pytest.mark.asyncio
    async def test_send_heartbeat(self, sse_service):
        """Test heartbeat event generation."""
        heartbeat = await sse_service.send_heartbeat()
        
        assert "event: heartbeat\n" in heartbeat
        assert "data: " in heartbeat
        assert "timestamp" in heartbeat
    
    def test_cleanup(self, sse_service):
        """Test cleanup method."""
        sse_service.cleanup()
        assert sse_service.client is None
    
    @pytest.mark.asyncio
    async def test_invoke_agent_streaming(self, sse_service, mock_boto3_client):
        """Test _invoke_agent_streaming method."""
        mock_boto3_client.invoke_agent.return_value = {
            'completion': [],
            'sessionId': 'test-session'
        }
        
        response = await sse_service._invoke_agent_streaming(
            agent_id="test-agent",
            agent_alias_id="test-alias",
            session_id="test-session",
            user_input="test input"
        )
        
        assert response is not None
        assert 'completion' in response
        
        # Verify correct parameters were passed
        mock_boto3_client.invoke_agent.assert_called_once()
        call_kwargs = mock_boto3_client.invoke_agent.call_args[1]
        assert call_kwargs['agentId'] == "test-agent"
        assert call_kwargs['agentAliasId'] == "test-alias"
        assert call_kwargs['sessionId'] == "test-session"
        assert call_kwargs['inputText'] == "test input"
    
    @pytest.mark.asyncio
    async def test_process_response_stream_empty(self, sse_service):
        """Test processing empty response stream."""
        response = {'completion': []}
        
        events = []
        async for event in sse_service._process_response_stream(response, "test-id"):
            events.append(event)
        
        assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_process_response_stream_with_empty_chunk(self, sse_service):
        """Test processing stream with empty chunk."""
        response = {
            'completion': [
                {'chunk': {'bytes': b''}}
            ]
        }
        
        events = []
        async for event in sse_service._process_response_stream(response, "test-id"):
            events.append(event)
        
        # Empty chunks should be skipped
        assert len(events) == 0
    
    def test_stream_event_types(self):
        """Test all StreamEventType enum values."""
        assert StreamEventType.START.value == "start"
        assert StreamEventType.CHUNK.value == "chunk"
        assert StreamEventType.THINKING.value == "thinking"
        assert StreamEventType.TOOL_USE.value == "tool_use"
        assert StreamEventType.COMPLETE.value == "complete"
        assert StreamEventType.ERROR.value == "error"
        assert StreamEventType.HEARTBEAT.value == "heartbeat"


class TestSSEStreamingServiceIntegration:
    """Integration tests for SSE Streaming Service."""
    
    @pytest.mark.asyncio
    async def test_full_streaming_workflow(self):
        """Test complete streaming workflow."""
        with patch('boto3.client') as mock_client:
            mock_agentcore_client = Mock()
            mock_client.return_value = mock_agentcore_client
            
            # Mock complete response
            mock_agentcore_client.invoke_agent.return_value = {
                'completion': [
                    {'chunk': {'bytes': b'The '}},
                    {'trace': {'thinking': 'Processing request...'}},
                    {'chunk': {'bytes': b'answer '}},
                    {'chunk': {'bytes': b'is 42.'}}
                ]
            }
            
            service = SSEStreamingService(region="us-east-1")
            
            events = []
            async for event in service.stream_agent_response(
                agent_id="test-agent",
                agent_alias_id="test-alias",
                session_id="test-session",
                user_input="What is the answer?",
                enable_trace=True
            ):
                events.append(event)
            
            # Verify event sequence
            assert len(events) >= 6  # start + chunks + thinking + complete
            
            # Verify start event
            assert "event: start\n" in events[0]
            
            # Verify chunk events
            chunk_events = [e for e in events if "event: chunk\n" in e]
            assert len(chunk_events) == 3
            
            # Verify thinking event
            thinking_events = [e for e in events if "event: thinking\n" in e]
            assert len(thinking_events) == 1
            
            # Verify complete event
            assert "event: complete\n" in events[-1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
