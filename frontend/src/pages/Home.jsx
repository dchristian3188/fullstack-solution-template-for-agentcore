import React, { useState, useRef, useEffect } from 'react';
import {
  AppLayout,
  ContentLayout,
  Header,
  Container,
  SpaceBetween,
  Input,
  Button,
  Box,
  Alert,
} from '@cloudscape-design/components';
import { invokeAgentCore, generateSessionId } from '../services/agentCoreService';
import { APP_NAME } from '../common/constants';

const HomePage = () => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const sessionId = useRef(generateSessionId());
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      id: generateSessionId(),
      role: 'user',
      content: inputValue.trim(),
    };

    const assistantMessage = {
      id: generateSessionId(),
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      await invokeAgentCore(userMessage.content, sessionId.current, (streamedContent) => {
        setMessages((prev) =>
          prev.map((msg) => (msg.id === assistantMessage.id ? { ...msg, content: streamedContent } : msg)),
        );
      });

      // Mark streaming as complete
      setMessages((prev) => prev.map((msg) => (msg.id === assistantMessage.id ? { ...msg, isStreaming: false } : msg)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      // Remove the failed assistant message
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantMessage.id));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.detail.key === 'Enter' && !event.detail.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  return (
    <AppLayout
      navigationHide
      toolsHide
      content={
        <ContentLayout
          header={
            <Header variant="h1" description="Chat with your AgentCore runtime">
              {APP_NAME}
            </Header>
          }
        >
          <Container>
            <SpaceBetween direction="vertical" size="l">
              {error && (
                <Alert type="error" dismissible onDismiss={() => setError(null)}>
                  {error}
                </Alert>
              )}

              <div
                style={{
                  minHeight: '400px',
                  maxHeight: '600px',
                  overflowY: 'auto',
                  border: '1px solid #e9ebed',
                  borderRadius: '8px',
                  backgroundColor: '#fafbfc',
                  padding: '16px',
                }}
              >
                <SpaceBetween direction="vertical" size="s">
                  {messages.length === 0 && (
                    <Box textAlign="center" color="text-body-secondary">
                      Start a conversation with your agent
                    </Box>
                  )}

                  {messages.map((message) => (
                    <div
                      key={message.id}
                      style={{
                        backgroundColor: message.role === 'user' ? '#e3f2fd' : '#f5f5f5',
                        borderRadius: '8px',
                        marginLeft: message.role === 'user' ? '20%' : '0',
                        marginRight: message.role === 'assistant' ? '20%' : '0',
                        padding: '12px',
                      }}
                    >
                      <Box fontSize="body-s" fontWeight="bold" color="text-label">
                        {message.role === 'user' ? 'You' : 'Agent'}
                        {message.isStreaming && ' (typing...)'}
                      </Box>
                      <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {message.content || (message.isStreaming ? '...' : '')}
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </SpaceBetween>
              </div>

              <SpaceBetween direction="horizontal" size="s">
                <Input
                  value={inputValue}
                  onChange={({ detail }) => setInputValue(detail.value)}
                  onKeyDown={handleKeyPress}
                  placeholder="Type your message..."
                  disabled={isLoading}
                />
                <Button
                  variant="primary"
                  onClick={handleSubmit}
                  disabled={!inputValue.trim() || isLoading}
                  loading={isLoading}
                >
                  Send
                </Button>
              </SpaceBetween>
            </SpaceBetween>
          </Container>
        </ContentLayout>
      }
    />
  );
};

export default HomePage;
