/**
 * Enhanced sendMessage function with SSE streaming support
 * 
 * This file provides an updated sendMessage function that supports both:
 * 1. Regular API calls (original functionality)
 * 2. SSE streaming for long-running agent invocations
 * 
 * To integrate: Replace the existing sendMessage function in index.html with this one.
 */

// Global SSE client instance
window.sseClient = null;

async function sendMessageEnhanced() {
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const errorDiv = document.getElementById('chatError');
    const awsAccountIdInput = document.getElementById('awsAccountId');
    const enableStreamingCheckbox = document.getElementById('enableStreaming');

    const message = input.value.trim();
    if (!message) return;

    const awsAccountId = awsAccountIdInput ? awsAccountIdInput.value.trim() : '';
    const enableStreaming = enableStreamingCheckbox && enableStreamingCheckbox.checked;

    // Add agent targeting identifier to user message
    let userMessageWithAgent = message;
    if (typeof selectedAgent !== 'undefined' && selectedAgent !== 'auto' && 
        typeof availableAgents !== 'undefined' && availableAgents[selectedAgent]) {
        const agentName = formatAgentName(selectedAgent);
        const agentStatus = availableAgents[selectedAgent].status === 'HEALTHY' ? '✅' : '⚠️';
        userMessageWithAgent = `${message} <span style="font-size: 0.8em; color: #666; font-style: italic;">→ ${agentStatus} ${agentName} (Manual)</span>`;
    } else {
        userMessageWithAgent = `${message} <span style="font-size: 0.8em; color: #666; font-style: italic;">→ 🤖 Auto-Select</span>`;
    }
    
    addMessage('user', userMessageWithAgent);
    input.value = '';
    sendBtn.disabled = true;
    sendBtn.textContent = enableStreaming ? 'Streaming...' : 'Sending...';
    if (errorDiv) errorDiv.textContent = '';

    // Check if streaming is enabled
    if (enableStreaming) {
        await sendMessageWithStreaming(message, awsAccountId, sendBtn, errorDiv);
    } else {
        await sendMessageRegular(message, awsAccountId, sendBtn, errorDiv);
    }
}

async function sendMessageWithStreaming(message, awsAccountId, sendBtn, errorDiv) {
    try {
        // Initialize SSE streaming client
        if (!window.sseClient) {
            window.sseClient = new SSEStreamingClient();
        }

        const sessionId = 'web-session-' + Date.now();

        // Prepare request options
        const options = {
            context: {},
            agent_id: null, // Will be filled by backend from context
            enable_trace: false
        };

        // Include AWS Account ID if provided
        if (awsAccountId) {
            options.context.aws_account_id = awsAccountId;
        }

        // Include selected agent information
        if (typeof selectedAgent !== 'undefined' && selectedAgent !== 'auto' && 
            typeof availableAgents !== 'undefined' && availableAgents[selectedAgent]) {
            options.context.selected_agent = selectedAgent;
            options.context.agent_selection_mode = 'manual';
            
            const agentName = formatAgentName(selectedAgent);
            message = `[Agent Selection: ${agentName} (${selectedAgent})] ${message}`;
            
            console.log(`🎯 Manual agent selection: ${selectedAgent}`);
        } else {
            options.context.agent_selection_mode = 'auto';
            console.log(`🤖 Auto agent selection enabled`);
        }

        // Create a placeholder message for streaming content
        const messagesContainer = document.getElementById('messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant-message';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = '<span class="streaming-indicator">⚡ Streaming response...</span>';
        
        messageDiv.appendChild(contentDiv);
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        let accumulatedContent = '';

        // Start streaming
        await window.sseClient.startStreaming(
            message,
            sessionId,
            options,
            // onChunk callback
            (chunk, accumulated, metadata) => {
                accumulatedContent = accumulated;
                
                // Update the message with accumulated content
                if (metadata && metadata.thinking) {
                    contentDiv.innerHTML = `
                        <div style="color: #666; font-style: italic; margin-bottom: 10px;">
                            💭 ${metadata.thinking}
                        </div>
                        ${processContentWithMarkdown(accumulated)}
                    `;
                } else if (metadata && metadata.tool_use) {
                    contentDiv.innerHTML = `
                        <div style="color: #666; font-style: italic; margin-bottom: 10px;">
                            🔧 Using tool: ${metadata.tool_use.name || 'Unknown'}
                        </div>
                        ${processContentWithMarkdown(accumulated)}
                    `;
                } else {
                    contentDiv.innerHTML = processContentWithMarkdown(accumulated);
                }
                
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            },
            // onComplete callback
            (finalContent) => {
                console.log('✅ Streaming completed');
                contentDiv.innerHTML = processContentWithMarkdown(finalContent);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                sendBtn.disabled = false;
                sendBtn.textContent = 'Send';
            },
            // onError callback
            (error) => {
                console.error('❌ Streaming error:', error);
                if (errorDiv) errorDiv.textContent = 'Streaming failed. Please try again.';
                contentDiv.innerHTML = `<span style="color: #dc3545;">Sorry, I encountered an error during streaming: ${error.message}</span>`;
                sendBtn.disabled = false;
                sendBtn.textContent = 'Send';
            }
        );

    } catch (error) {
        console.error('Chat streaming error:', error);
        if (errorDiv) errorDiv.textContent = 'Failed to start streaming. Please try again.';
        addMessage('assistant', 'Sorry, I encountered an error with streaming. Please try again or disable streaming mode.');
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
    }
}

async function sendMessageRegular(message, awsAccountId, sendBtn, errorDiv) {
    try {
        // Prepare the request body with proper agent selection context
        const requestBody = {
            message: message,
            session_id: 'web-session-' + Date.now(),
            context: {}
        };

        // Include AWS Account ID if provided
        if (awsAccountId) {
            requestBody.context.aws_account_id = awsAccountId;
        }

        // Include selected agent information in context for backend processing
        if (typeof selectedAgent !== 'undefined' && selectedAgent !== 'auto' && 
            typeof availableAgents !== 'undefined' && availableAgents[selectedAgent]) {
            requestBody.context.selected_agent = selectedAgent;
            requestBody.context.agent_selection_mode = 'manual';
            
            // Also add agent selection hint to the message for LLM context
            const agentName = formatAgentName(selectedAgent);
            requestBody.message = `[Agent Selection: ${agentName} (${selectedAgent})] ${message}`;
            
            console.log(`🎯 Manual agent selection: ${selectedAgent}`);
            console.log(`Context:`, requestBody.context);
        } else {
            requestBody.context.agent_selection_mode = 'auto';
            console.log(`🤖 Auto agent selection enabled`);
        }

        // Debug: Log the complete request
        console.log('📤 Request body:', JSON.stringify(requestBody, null, 2));

        const backendUrl = window.API_CONFIG?.BACKEND_URL || 'http://localhost:8000';
        const response = await fetch(`${backendUrl}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Handle structured responses with JSON data
        if (data.structured_data) {
            addMessage('assistant', data.response || 'Analysis completed.', [], data.structured_data, data.human_summary);
        } else {
            addMessage('assistant', data.response || 'I received your message but had no response.');
        }

    } catch (error) {
        console.error('Chat error:', error);
        if (errorDiv) errorDiv.textContent = 'Failed to send message. Please try again.';
        addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
    }
}

// Override the original sendMessage function
if (typeof window !== 'undefined') {
    window.sendMessage = sendMessageEnhanced;
}
