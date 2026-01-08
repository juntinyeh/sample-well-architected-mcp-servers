"""
Unit tests for AgentCore app streaming endpoints.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


class TestAgentCoreStreamingEndpoints:
    """Test suite for AgentCore streaming endpoints."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services dictionary."""
        return {
            "config": Mock(),
            "auth": Mock(),
            "aws_config": Mock(),
            "version_config": Mock(),
            "bedrock_model": Mock(),
            "mode": "full"
        }
    
    @pytest.fixture
    def app_with_mocks(self, mock_services):
        """Create FastAPI app with mocked services."""
        with patch('agentcore.app.initialize_agentcore_services') as mock_init:
            mock_init.return_value = mock_services
            
            with patch('agentcore.app.validate_aws_connectivity', new_callable=AsyncMock):
                with patch('agentcore.app.initialize_agent_services', new_callable=AsyncMock):
                    from agentcore.app import create_agentcore_app
                    app = create_agentcore_app()
                    
                    # Add mock services to app state for testing
                    app.state.services = mock_services
                    
                    yield app
    
    def test_health_check_endpoint(self, app_with_mocks):
        """Test health check endpoint."""
        client = TestClient(app_with_mocks)
        
        # Mock health check methods
        app_with_mocks.state.services["version_config"].health_check = AsyncMock(return_value="healthy")
        app_with_mocks.state.services["bedrock_model"].health_check = AsyncMock(return_value="healthy")
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert data["version"] == "agentcore"
        assert "services" in data
    
    def test_version_endpoint(self, app_with_mocks):
        """Test version info endpoint."""
        client = TestClient(app_with_mocks)
        
        # Mock version service
        mock_version_summary = {
            "backend_type": "agentcore",
            "capabilities": ["streaming", "agents"]
        }
        app_with_mocks.state.services["version_config"].get_version_summary = Mock(
            return_value=mock_version_summary
        )
        
        response = client.get("/api/version")
        
        assert response.status_code == 200
        data = response.json()
        assert data["backend_version"] == "agentcore"
        assert "version_info" in data
    
    def test_config_status_endpoint(self, app_with_mocks):
        """Test config status endpoint."""
        client = TestClient(app_with_mocks)
        
        # Mock config methods
        app_with_mocks.state.services["config"].get_ssm_status = Mock(
            return_value={"connected": True}
        )
        app_with_mocks.state.services["version_config"].get_version_config = Mock(
            return_value={"version": "1.0.0"}
        )
        app_with_mocks.state.services["version_config"].get_feature_flags = Mock(
            return_value={"streaming": True}
        )
        app_with_mocks.state.services["version_config"].get_service_flags = Mock(
            return_value={"agentcore": True}
        )
        
        response = client.get("/api/config/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "config" in data
    
    @pytest.mark.asyncio
    async def test_chat_stream_endpoint_with_agent_id(self):
        """Test SSE streaming endpoint with agent_id."""
        with patch('agentcore.app.initialize_agentcore_services') as mock_init:
            mock_services = {
                "config": Mock(),
                "mode": "full"
            }
            mock_services["config"].get_config_value = Mock(return_value="us-east-1")
            mock_init.return_value = mock_services
            
            with patch('agentcore.app.validate_aws_connectivity', new_callable=AsyncMock):
                with patch('agentcore.app.initialize_agent_services', new_callable=AsyncMock):
                    from agentcore.app import create_agentcore_app
                    app = create_agentcore_app()
                    
                    # Mock SSE streaming service
                    with patch('agentcore.services.sse_streaming_service.SSEStreamingService') as mock_sse_class:
                        mock_sse = Mock()
                        
                        async def mock_stream(*args, **kwargs):
                            yield "event: start\ndata: {}\n\n"
                            yield "event: chunk\ndata: {\"content\": \"test\"}\n\n"
                            yield "event: complete\ndata: {}\n\n"
                        
                        mock_sse.stream_agent_response = mock_stream
                        mock_sse_class.return_value = mock_sse
                        
                        client = TestClient(app)
                        
                        response = client.post(
                            "/api/chat/stream",
                            json={
                                "message": "test message",
                                "session_id": "test-session",
                                "agent_id": "test-agent",
                                "agent_alias_id": "test-alias"
                            },
                            headers={"Accept": "text/event-stream"}
                        )
                        
                        assert response.status_code == 200
                        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
    def test_chat_stream_endpoint_missing_message(self, app_with_mocks):
        """Test SSE streaming endpoint with missing message."""
        client = TestClient(app_with_mocks)
        
        response = client.post(
            "/api/chat/stream",
            json={
                "session_id": "test-session"
            }
        )
        
        assert response.status_code == 400
        assert "Message is required" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_chat_stream_endpoint_fallback_mode(self):
        """Test SSE streaming endpoint fallback to regular orchestrator."""
        with patch('agentcore.app.initialize_agentcore_services') as mock_init:
            mock_services = {
                "config": Mock(),
                "mode": "full",
                "strands_orchestrator": Mock()
            }
            mock_services["config"].get_config_value = Mock(return_value="us-east-1")
            
            # Mock orchestrator response
            async def mock_process_message(*args, **kwargs):
                return {
                    "content": "Test response from orchestrator"
                }
            
            mock_services["strands_orchestrator"].process_message = mock_process_message
            mock_init.return_value = mock_services
            
            with patch('agentcore.app.validate_aws_connectivity', new_callable=AsyncMock):
                with patch('agentcore.app.initialize_agent_services', new_callable=AsyncMock):
                    from agentcore.app import create_agentcore_app
                    app = create_agentcore_app()
                    
                    client = TestClient(app)
                    
                    # Mock SSE streaming service
                    with patch('agentcore.services.sse_streaming_service.SSEStreamingService') as mock_sse_class:
                        mock_sse = Mock()
                        mock_sse.format_sse_event = Mock(return_value="event: test\ndata: {}\n\n")
                        mock_sse_class.return_value = mock_sse
                        
                        response = client.post(
                            "/api/chat/stream",
                            json={
                                "message": "test message",
                                "session_id": "test-session"
                            },
                            headers={"Accept": "text/event-stream"}
                        )
                        
                        assert response.status_code == 200


class TestAgentCoreRegularEndpoints:
    """Test suite for regular (non-streaming) AgentCore endpoints."""
    
    @pytest.fixture
    def mock_services_minimal(self):
        """Create mock services for minimal mode."""
        mock_bedrock = Mock()
        mock_bedrock.health_check = AsyncMock(return_value="healthy")
        mock_bedrock.get_standard_model = Mock(return_value="claude-3-sonnet")
        mock_bedrock.invoke_model = AsyncMock(return_value={"content": "test response"})
        mock_bedrock.format_response = Mock(return_value={
            "content": "test response",
            "metadata": {}
        })
        
        mock_version = Mock()
        mock_version.health_check = AsyncMock(return_value="healthy")
        
        return {
            "config": Mock(),
            "auth": Mock(),
            "aws_config": Mock(),
            "version_config": mock_version,
            "bedrock_model": mock_bedrock,
            "mode": "minimal"
        }
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_minimal_mode(self, mock_services_minimal):
        """Test regular chat endpoint in minimal mode."""
        with patch('agentcore.app.initialize_agentcore_services') as mock_init:
            mock_init.return_value = mock_services_minimal
            
            with patch('agentcore.app.validate_aws_connectivity', new_callable=AsyncMock):
                with patch('agentcore.app.validate_bedrock_model_service', new_callable=AsyncMock):
                    from agentcore.app import create_agentcore_app_minimal
                    app = create_agentcore_app_minimal()
                    
                    client = TestClient(app)
                    
                    response = client.post(
                        "/api/chat",
                        json={
                            "message": "test message",
                            "session_id": "test-session"
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "response" in data
                    assert data["response_type"] == "model_fallback"
    
    @pytest.mark.asyncio
    async def test_model_invoke_endpoint(self, mock_services_minimal):
        """Test direct model invocation endpoint."""
        with patch('agentcore.app.initialize_agentcore_services') as mock_init:
            mock_init.return_value = mock_services_minimal
            
            with patch('agentcore.app.validate_aws_connectivity', new_callable=AsyncMock):
                with patch('agentcore.app.validate_bedrock_model_service', new_callable=AsyncMock):
                    from agentcore.app import create_agentcore_app_minimal
                    app = create_agentcore_app_minimal()
                    
                    client = TestClient(app)
                    
                    response = client.post(
                        "/api/model/invoke",
                        json={
                            "message": "test message",
                            "model_id": "claude-3-sonnet"
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "response" in data
                    assert "model_id" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
