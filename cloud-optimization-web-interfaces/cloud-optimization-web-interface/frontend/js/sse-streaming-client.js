/**
 * SSE Streaming Client for AgentCore Runtime
 * 
 * Handles Server-Sent Events (SSE) streaming for long-running agent invocations.
 * Provides real-time response updates with proper error handling and reconnection.
 */

class SSEStreamingClient {
    constructor() {
        this.eventSource = null;
        this.currentMessageElement = null;
        this.accumulatedContent = '';
        this.isStreaming = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
    }

    /**
     * Start SSE streaming for a chat message
     * @param {string} message - User message
     * @param {string} sessionId - Session ID
     * @param {Object} options - Additional options (agent_id, enable_trace, etc.)
     * @param {Function} onChunk - Callback for each chunk received
     * @param {Function} onComplete - Callback when streaming completes
     * @param {Function} onError - Callback for errors
     */
    async startStreaming(message, sessionId, options = {}, onChunk, onComplete, onError) {
        try {
            this.isStreaming = true;
            this.accumulatedContent = '';

            // Get the backend URL from config
            const backendUrl = window.API_CONFIG?.BACKEND_URL || 'http://localhost:8000';
            const streamEndpoint = `${backendUrl}/api/chat/stream`;

            // Prepare request body
            const requestBody = {
                message: message,
                session_id: sessionId,
                agent_id: options.agent_id || null,
                agent_alias_id: options.agent_alias_id || 'TSTALIASID',
                enable_trace: options.enable_trace || false,
                timeout: options.timeout || 300,
                context: options.context || {}
            };

            // Use fetch with ReadableStream for SSE
            const response = await fetch(streamEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream',
                    'Authorization': options.authToken ? `Bearer ${options.authToken}` : ''
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Process the stream
            await this.processStream(response.body, onChunk, onComplete, onError);

        } catch (error) {
            console.error('SSE Streaming error:', error);
            this.isStreaming = false;
            if (onError) {
                onError(error);
            }
        }
    }

    /**
     * Process the SSE stream
     * @param {ReadableStream} stream - Response body stream
     * @param {Function} onChunk - Chunk callback
     * @param {Function} onComplete - Complete callback
     * @param {Function} onError - Error callback
     */
    async processStream(stream, onChunk, onComplete, onError) {
        const reader = stream.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        try {
            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    console.log('Stream complete');
                    break;
                }

                // Decode chunk and add to buffer
                buffer += decoder.decode(value, { stream: true });

                // Process complete SSE events in buffer
                const events = this.parseSSEEvents(buffer);
                
                for (const event of events.parsed) {
                    await this.handleSSEEvent(event, onChunk, onComplete, onError);
                }

                // Keep remaining incomplete data in buffer
                buffer = events.remaining;
            }

            // Handle any remaining complete event in buffer
            if (buffer.trim()) {
                const finalEvents = this.parseSSEEvents(buffer + '\n\n');
                for (const event of finalEvents.parsed) {
                    await this.handleSSEEvent(event, onChunk, onComplete, onError);
                }
            }

        } catch (error) {
            console.error('Stream processing error:', error);
            if (onError) {
                onError(error);
            }
        } finally {
            reader.releaseLock();
            this.isStreaming = false;
        }
    }

    /**
     * Parse SSE events from buffer
     * @param {string} buffer - Buffer containing SSE data
     * @returns {Object} Parsed events and remaining buffer
     */
    parseSSEEvents(buffer) {
        const events = [];
        const lines = buffer.split('\n');
        let currentEvent = { type: null, data: null, id: null };
        let i = 0;

        while (i < lines.length) {
            const line = lines[i];

            if (line.trim() === '') {
                // Empty line indicates end of event
                if (currentEvent.type && currentEvent.data !== null) {
                    events.push({ ...currentEvent });
                }
                currentEvent = { type: null, data: null, id: null };
                i++;
                continue;
            }

            if (line.startsWith('event:')) {
                currentEvent.type = line.substring(6).trim();
            } else if (line.startsWith('data:')) {
                const data = line.substring(5).trim();
                currentEvent.data = currentEvent.data ? currentEvent.data + '\n' + data : data;
            } else if (line.startsWith('id:')) {
                currentEvent.id = line.substring(3).trim();
            } else if (line.startsWith(':')) {
                // Comment line, ignore
            }

            i++;
        }

        // Calculate remaining buffer (incomplete event)
        let remaining = '';
        if (currentEvent.type || currentEvent.data) {
            // Reconstruct incomplete event
            if (currentEvent.type) remaining += `event: ${currentEvent.type}\n`;
            if (currentEvent.id) remaining += `id: ${currentEvent.id}\n`;
            if (currentEvent.data) remaining += `data: ${currentEvent.data}\n`;
        }

        return { parsed: events, remaining: remaining };
    }

    /**
     * Handle individual SSE event
     * @param {Object} event - Parsed SSE event
     * @param {Function} onChunk - Chunk callback
     * @param {Function} onComplete - Complete callback
     * @param {Function} onError - Error callback
     */
    async handleSSEEvent(event, onChunk, onComplete, onError) {
        console.log('SSE Event:', event.type, event.data);

        try {
            let data = {};
            
            // Try to parse data as JSON
            if (event.data) {
                try {
                    data = JSON.parse(event.data);
                } catch (e) {
                    // If not JSON, use as plain text
                    data = { content: event.data };
                }
            }

            switch (event.type) {
                case 'start':
                    console.log('Stream started:', data.invocation_id);
                    break;

                case 'chunk':
                    if (data.content) {
                        this.accumulatedContent += data.content;
                        if (onChunk) {
                            onChunk(data.content, this.accumulatedContent);
                        }
                    }
                    break;

                case 'thinking':
                    console.log('Agent thinking:', data.thinking);
                    if (onChunk) {
                        onChunk('', this.accumulatedContent, { thinking: data.thinking });
                    }
                    break;

                case 'tool_use':
                    console.log('Tool use:', data.tool_use);
                    if (onChunk) {
                        onChunk('', this.accumulatedContent, { tool_use: data.tool_use });
                    }
                    break;

                case 'complete':
                    console.log('Stream completed');
                    this.isStreaming = false;
                    if (onComplete) {
                        onComplete(this.accumulatedContent);
                    }
                    break;

                case 'error':
                    console.error('Stream error:', data.error_message);
                    this.isStreaming = false;
                    if (onError) {
                        onError(new Error(data.error_message || 'Stream error'));
                    }
                    break;

                case 'heartbeat':
                    // Keep-alive heartbeat, no action needed
                    console.log('Heartbeat received');
                    break;

                default:
                    console.warn('Unknown event type:', event.type);
            }

        } catch (error) {
            console.error('Error handling SSE event:', error);
            if (onError) {
                onError(error);
            }
        }
    }

    /**
     * Stop the current streaming session
     */
    stopStreaming() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.isStreaming = false;
        this.accumulatedContent = '';
    }

    /**
     * Check if currently streaming
     * @returns {boolean}
     */
    isCurrentlyStreaming() {
        return this.isStreaming;
    }

    /**
     * Get accumulated content
     * @returns {string}
     */
    getAccumulatedContent() {
        return this.accumulatedContent;
    }
}

// Export for use in other modules
window.SSEStreamingClient = SSEStreamingClient;
