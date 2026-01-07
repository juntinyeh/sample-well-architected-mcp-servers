#!/usr/bin/env python3
"""
End-to-End Integration Test for COA AgentCore Streaming

This script validates the complete flow from frontend to backend to AgentCore invocation,
including SSE streaming functionality.

Usage:
    python3 e2e_integration_test.py [--backend-url URL] [--test-streaming] [--verbose]
"""

import argparse
import asyncio
import json
import sys
import time
from typing import Dict, List, Any
import requests
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class E2EIntegrationTest:
    """End-to-end integration test suite."""
    
    def __init__(self, backend_url: str = "http://localhost:8000", verbose: bool = False):
        """
        Initialize the test suite.
        
        Args:
            backend_url: Backend service URL
            verbose: Enable verbose logging
        """
        self.backend_url = backend_url.rstrip('/')
        self.verbose = verbose
        self.results = []
        
    def log(self, message: str, color: str = Colors.BLUE):
        """Log a message with color."""
        print(f"{color}{message}{Colors.ENDC}")
    
    def log_success(self, message: str):
        """Log a success message."""
        self.log(f"✅ {message}", Colors.GREEN)
    
    def log_error(self, message: str):
        """Log an error message."""
        self.log(f"❌ {message}", Colors.RED)
    
    def log_warning(self, message: str):
        """Log a warning message."""
        self.log(f"⚠️  {message}", Colors.YELLOW)
    
    def log_info(self, message: str):
        """Log an info message."""
        self.log(f"ℹ️  {message}", Colors.BLUE)
    
    def test_backend_health(self) -> bool:
        """Test backend health endpoint."""
        self.log_info("Testing backend health endpoint...")
        
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if self.verbose:
                    self.log_info(f"Health response: {json.dumps(data, indent=2)}")
                
                if data.get('status') in ['healthy', 'degraded']:
                    self.log_success(f"Backend is {data.get('status')}")
                    self.results.append(("Health Check", True, None))
                    return True
                else:
                    self.log_error(f"Backend status: {data.get('status')}")
                    self.results.append(("Health Check", False, f"Unhealthy status: {data.get('status')}"))
                    return False
            else:
                self.log_error(f"Health check failed with status {response.status_code}")
                self.results.append(("Health Check", False, f"HTTP {response.status_code}"))
                return False
                
        except Exception as e:
            self.log_error(f"Health check error: {e}")
            self.results.append(("Health Check", False, str(e)))
            return False
    
    def test_config_endpoint(self) -> bool:
        """Test configuration endpoint."""
        self.log_info("Testing configuration endpoint...")
        
        try:
            response = requests.get(f"{self.backend_url}/api/config/status", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if self.verbose:
                    self.log_info(f"Config response: {json.dumps(data, indent=2)}")
                
                self.log_success("Configuration endpoint working")
                self.results.append(("Config Endpoint", True, None))
                return True
            else:
                self.log_error(f"Config check failed with status {response.status_code}")
                self.results.append(("Config Endpoint", False, f"HTTP {response.status_code}"))
                return False
                
        except Exception as e:
            self.log_error(f"Config check error: {e}")
            self.results.append(("Config Endpoint", False, str(e)))
            return False
    
    def test_regular_chat(self) -> bool:
        """Test regular chat endpoint."""
        self.log_info("Testing regular chat endpoint...")
        
        try:
            payload = {
                "message": "Hello, this is a test message",
                "session_id": f"test-session-{int(time.time())}",
                "context": {}
            }
            
            response = requests.post(
                f"{self.backend_url}/api/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if self.verbose:
                    self.log_info(f"Chat response: {json.dumps(data, indent=2)}")
                
                if 'response' in data:
                    self.log_success(f"Regular chat working - Response length: {len(data['response'])}")
                    self.results.append(("Regular Chat", True, None))
                    return True
                else:
                    self.log_error("No response field in chat data")
                    self.results.append(("Regular Chat", False, "Missing response field"))
                    return False
            else:
                self.log_error(f"Chat failed with status {response.status_code}")
                self.results.append(("Regular Chat", False, f"HTTP {response.status_code}"))
                return False
                
        except Exception as e:
            self.log_error(f"Chat error: {e}")
            self.results.append(("Regular Chat", False, str(e)))
            return False
    
    async def test_streaming_chat(self) -> bool:
        """Test SSE streaming chat endpoint."""
        self.log_info("Testing SSE streaming chat endpoint...")
        
        try:
            import aiohttp
            
            payload = {
                "message": "Test streaming response",
                "session_id": f"test-stream-{int(time.time())}",
                "context": {}
            }
            
            timeout = aiohttp.ClientTimeout(total=60)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.backend_url}/api/chat/stream",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream"
                    }
                ) as response:
                    
                    if response.status == 200:
                        events_received = []
                        content_chunks = []
                        
                        # Read SSE stream
                        async for line in response.content:
                            line_str = line.decode('utf-8').strip()
                            
                            if self.verbose and line_str:
                                self.log_info(f"SSE Line: {line_str}")
                            
                            if line_str.startswith('event:'):
                                event_type = line_str.split(':', 1)[1].strip()
                                events_received.append(event_type)
                            elif line_str.startswith('data:'):
                                data_str = line_str.split(':', 1)[1].strip()
                                try:
                                    data = json.loads(data_str)
                                    if 'content' in data:
                                        content_chunks.append(data['content'])
                                except json.JSONDecodeError:
                                    pass
                        
                        if self.verbose:
                            self.log_info(f"Events received: {events_received}")
                            self.log_info(f"Content chunks: {len(content_chunks)}")
                        
                        # Validate streaming
                        if 'start' in events_received and 'complete' in events_received:
                            self.log_success(f"Streaming working - Received {len(events_received)} events")
                            self.results.append(("Streaming Chat", True, None))
                            return True
                        else:
                            self.log_warning(f"Streaming incomplete - Events: {events_received}")
                            self.results.append(("Streaming Chat", False, f"Missing start/complete events"))
                            return False
                    else:
                        self.log_error(f"Streaming failed with status {response.status}")
                        self.results.append(("Streaming Chat", False, f"HTTP {response.status}"))
                        return False
                        
        except ImportError:
            self.log_warning("aiohttp not installed, skipping streaming test")
            self.results.append(("Streaming Chat", None, "aiohttp not available"))
            return False
        except Exception as e:
            self.log_error(f"Streaming error: {e}")
            self.results.append(("Streaming Chat", False, str(e)))
            return False
    
    def test_agent_status(self) -> bool:
        """Test agent status endpoint."""
        self.log_info("Testing agent status endpoint...")
        
        try:
            response = requests.get(f"{self.backend_url}/api/agents/status", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if self.verbose:
                    self.log_info(f"Agent status: {json.dumps(data, indent=2)}")
                
                agent_count = data.get('count', 0)
                self.log_success(f"Agent status endpoint working - {agent_count} agents found")
                self.results.append(("Agent Status", True, None))
                return True
            elif response.status_code == 404:
                self.log_warning("Agent status endpoint not available (minimal mode)")
                self.results.append(("Agent Status", None, "Not available in minimal mode"))
                return False
            else:
                self.log_error(f"Agent status failed with status {response.status_code}")
                self.results.append(("Agent Status", False, f"HTTP {response.status_code}"))
                return False
                
        except Exception as e:
            self.log_error(f"Agent status error: {e}")
            self.results.append(("Agent Status", False, str(e)))
            return False
    
    def print_summary(self):
        """Print test results summary."""
        self.log("\n" + "="*70, Colors.BOLD)
        self.log("TEST RESULTS SUMMARY", Colors.BOLD)
        self.log("="*70, Colors.BOLD)
        
        passed = sum(1 for _, result, _ in self.results if result is True)
        failed = sum(1 for _, result, _ in self.results if result is False)
        skipped = sum(1 for _, result, _ in self.results if result is None)
        total = len(self.results)
        
        for test_name, result, error in self.results:
            if result is True:
                self.log(f"✅ {test_name:<30} PASSED", Colors.GREEN)
            elif result is False:
                self.log(f"❌ {test_name:<30} FAILED", Colors.RED)
                if error:
                    self.log(f"   Error: {error}", Colors.RED)
            else:
                self.log(f"⏭️  {test_name:<30} SKIPPED", Colors.YELLOW)
                if error:
                    self.log(f"   Reason: {error}", Colors.YELLOW)
        
        self.log("\n" + "-"*70, Colors.BOLD)
        self.log(f"Total Tests: {total}", Colors.BOLD)
        self.log(f"Passed: {passed}", Colors.GREEN)
        self.log(f"Failed: {failed}", Colors.RED)
        self.log(f"Skipped: {skipped}", Colors.YELLOW)
        
        success_rate = (passed / total * 100) if total > 0 else 0
        self.log(f"Success Rate: {success_rate:.1f}%", Colors.BOLD)
        
        self.log("="*70 + "\n", Colors.BOLD)
        
        return failed == 0
    
    async def run_all_tests(self, test_streaming: bool = True) -> bool:
        """
        Run all integration tests.
        
        Args:
            test_streaming: Whether to test streaming functionality
            
        Returns:
            True if all tests passed
        """
        self.log("\n" + "="*70, Colors.BOLD)
        self.log("COA AGENTCORE E2E INTEGRATION TESTS", Colors.BOLD)
        self.log("="*70 + "\n", Colors.BOLD)
        
        self.log_info(f"Backend URL: {self.backend_url}")
        self.log_info(f"Test Streaming: {test_streaming}")
        self.log_info(f"Verbose: {self.verbose}\n")
        
        # Run tests
        self.test_backend_health()
        self.test_config_endpoint()
        self.test_regular_chat()
        
        if test_streaming:
            await self.test_streaming_chat()
        
        self.test_agent_status()
        
        # Print summary
        all_passed = self.print_summary()
        
        return all_passed


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="End-to-end integration tests for COA AgentCore Streaming"
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend service URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--test-streaming",
        action="store_true",
        default=True,
        help="Test SSE streaming functionality (default: True)"
    )
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Skip streaming tests"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    test_streaming = args.test_streaming and not args.no_streaming
    
    # Run tests
    test_suite = E2EIntegrationTest(
        backend_url=args.backend_url,
        verbose=args.verbose
    )
    
    all_passed = await test_suite.run_all_tests(test_streaming=test_streaming)
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
