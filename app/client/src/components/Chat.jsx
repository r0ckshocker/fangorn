import React, { useState, useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import axios from '../axiosSetup';
import { Upload, Send, Save, User, Bot } from 'lucide-react';
import '../styles/Chat.css';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_EXTENSIONS = ['.txt', '.pdf', '.doc', '.docx', '.csv', '.json', '.js', '.py', '.xml'];

const Chat = forwardRef(({ dashboard, conversationId, onUploadSuccess, onConversationChange }, ref) => {
    const [chatInput, setChatInput] = useState('');
    const [messages, setMessages] = useState([]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [file, setFile] = useState(null);
    const [uploadStatus, setUploadStatus] = useState('');
    const [currentConversationId, setCurrentConversationId] = useState(conversationId);
    const [fileUploaded, setFileUploaded] = useState(false);
    const [fileAnalysis, setFileAnalysis] = useState(null);
    const messagesEndRef = useRef(null);
    const [saveStatus, setSaveStatus] = useState('');

    useEffect(() => {
        hljs.highlightAll();
    }, [messages]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    useEffect(() => {
        if (conversationId !== currentConversationId) {
            setCurrentConversationId(conversationId);
            if (conversationId) {
                loadConversation(conversationId);
            } else {
                resetChat();
            }
        }
    }, [conversationId]);

    useImperativeHandle(ref, () => ({
        sendInvisibleMessage: async (message) => {
            if (!message) return;
            await sendSystemMessage(message);
        }
    }));

    const sendSystemMessage = async (message) => {
        if (!message || isGenerating) return;

        setIsGenerating(true);
        try {
            const response = await axios.post('/chat', {
                action: 'chat',
                prompt: message,
                dashboard_id: dashboard,
                conversation_id: currentConversationId,
                messages: messages,
                is_system_message: true
            });

            if (response.data.conversation_id && !currentConversationId) {
                setCurrentConversationId(response.data.conversation_id);
                if (onConversationChange) {
                    onConversationChange(response.data.conversation_id);
                }
            }
        } catch (error) {
            console.error('Error sending system message:', error);
        } finally {
            setIsGenerating(false);
        }
    };

    const MessageAvatar = ({ isUser }) => {
        return (
            <div className={`message-avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
                {isUser ? (
                    <User className="w-5 h-5 text-white" />
                ) : (
                    <Bot className="w-5 h-5 text-white" />
                )}
            </div>
        );
    };

    const Message = ({ message, isUserMessage }) => {
        return (
            <div className={`chat-message ${message.role}`}>
                <MessageAvatar isUser={isUserMessage} />
                <div className="message-content">
                    {message.role === 'user' ? (
                        <span dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }} />
                    ) : (
                        <span dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }} />
                    )}
                </div>
            </div>
        );
    };

    const saveConversation = async () => {
        if (!currentConversationId || !messages || messages.length === 0) {
            setSaveStatus('No conversation to save');
            setTimeout(() => setSaveStatus(''), 3000);
            return;
        }

        setSaveStatus('Saving conversation...');
        try {
            const response = await axios.post('/chat', {
                action: 'save',
                dashboard_id: dashboard,
                conversation_id: currentConversationId,
                messages: messages.filter(m => !m.invisible)
            });

            if (response.data.status === 'success') {
                setSaveStatus('Saved successfully');
            } else {
                setSaveStatus(response.data.error || 'Error saving conversation');
            }
        } catch (error) {
            console.error('Error saving conversation:', error);
            setSaveStatus('Failed to save conversation');
        }
        setTimeout(() => setSaveStatus(''), 3000);
    };

    const loadConversation = async (convId) => {
        if (!convId) return;

        setIsGenerating(true);
        try {
            const response = await axios.get(
                `/chat?action=get_conversation&dashboard_id=${dashboard}&conversation_id=${convId}`
            );

            // Handle both legacy and new response formats
            const messages = response.data?.messages?.messages || response.data?.messages || [];
            if (messages.length > 0) {
                setMessages(messages);
                setCurrentConversationId(convId);
            } else {
                console.error('No messages found in response:', response.data);
                resetChat();
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
            resetChat();
        } finally {
            setIsGenerating(false);
        }
    };

    const sendMessage = async () => {
        if ((chatInput.trim() === '' && !file) || isGenerating) return;

        setIsGenerating(true);
        const inputMessage = chatInput.trim();
        let currentMessages = [...messages].filter(m => !m.invisible);  // Change to let

        // Immediately add user message to the UI
        if (inputMessage) {
            const userMessage = { role: 'user', content: inputMessage };
            currentMessages = [...currentMessages, userMessage];  // Update currentMessages
            setMessages(currentMessages);  // Update UI
        }
        setChatInput('');

        try {
            let convId = currentConversationId;
            let fileName = null;

            // Handle file upload if selected
            if (file) {
                const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
                setUploadStatus('Preparing upload...');

                const response = await axios.post('/chat', {
                    action: 'get_upload_url',
                    file_extension: fileExtension,
                    dashboard_id: dashboard,
                    conversation_id: convId,
                    original_filename: file.name,
                });

                const { presigned_post, file_name, conversation_id: newConversationId } = response.data;

                if (newConversationId && !convId) {
                    convId = newConversationId;
                    setCurrentConversationId(newConversationId);
                    if (onConversationChange) {
                        onConversationChange(newConversationId);
                    }
                }

                const formData = new FormData();
                Object.entries(presigned_post.fields).forEach(([key, value]) => {
                    formData.append(key, value);
                });
                formData.append('file', file);

                setUploadStatus('Uploading file...');
                await axios.post(presigned_post.url, formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                });

                setUploadStatus('File uploaded successfully');
                fileName = file_name;
                setFileUploaded(true);
                if (onUploadSuccess) {
                    onUploadSuccess();
                }
            }

            if (inputMessage || fileName) {
                const chatData = {
                    action: 'chat',
                    prompt: inputMessage,
                    dashboard_id: dashboard,
                    conversation_id: convId,
                    messages: currentMessages,  // Use updated currentMessages
                    file_name: fileName,
                    is_system_message: false
                };

                const chatResponse = await axios.post('/chat', chatData);

                if (chatResponse.data.conversation_id && !convId) {
                    const newConvId = chatResponse.data.conversation_id;
                    setCurrentConversationId(newConvId);
                    if (onConversationChange) {
                        onConversationChange(newConvId);
                    }
                }

                if (chatResponse.data.file_analysis) {
                    // Store file analysis if needed
                    setFileAnalysis(chatResponse.data.file_analysis);
                }

                if (Array.isArray(chatResponse.data.messages)) {
                    const assistantMessage = chatResponse.data.messages[chatResponse.data.messages.length - 1];
                    if (assistantMessage && assistantMessage.role === 'assistant') {
                        setMessages([...currentMessages, assistantMessage]);
                    }
                }
            }
        } catch (error) {
            console.error('Error:', error);
            const errorMessage = { role: 'assistant', content: 'An error occurred. Please try again.' };
            setMessages([...currentMessages, errorMessage]);
        } finally {
            setIsGenerating(false);
            setFile(null);
            setUploadStatus('');
        }
    };

    const handleFileChange = (event) => {
        const selectedFile = event.target.files[0];
        if (!selectedFile) return;

        if (selectedFile.size > MAX_FILE_SIZE) {
            setUploadStatus('File too large. Maximum size is 10MB');
            return;
        }

        const fileExt = '.' + selectedFile.name.split('.').pop().toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(fileExt)) {
            setUploadStatus(`Unsupported file type. Allowed types: ${ALLOWED_EXTENSIONS.join(', ')}`);
            return;
        }

        setFile(selectedFile);
        setUploadStatus('');
    };

    const handleKeyPress = (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    };

    const resetChat = () => {
        setMessages([]);
        setCurrentConversationId(null);
        setFileUploaded(false);
        setChatInput('');
        setFile(null);
        setUploadStatus('');
    };

    const formatMessage = (content) => {
        return content.replace(/(?:\r\n|\r|\n)/g, '<br>');
    };

    const renderMarkdown = (content) => {
        return marked(content, {
            highlight: function (code, lang) {
                const language = hljs.getLanguage(lang) ? lang : 'plaintext';
                return hljs.highlight(code, { language }).value;
            },
            langPrefix: 'hljs language-'
        });
    };

    // Only show non-invisible messages in the UI
    const visibleMessages = messages.filter(message => !message.invisible);

    return (
        <div className="chat">
            <div className="chat-messages">
                {visibleMessages.map((message, index) => (
                    <Message
                        key={index}
                        message={message}
                        isUserMessage={message.role === 'user'}
                    />
                ))}
                {isGenerating && (
                    <div className="chat-message assistant loading">
                        <MessageAvatar isUser={false} />
                        <span className="loading-spinner">
                            <Send className="animate-spin" />
                        </span>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>
            <div className="chat-input">
                <textarea
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Type a message..."
                    rows={1}
                    disabled={isGenerating}
                />
                <div className="input-actions">
                    <label htmlFor="file-upload" className={`upload-label ${fileUploaded ? 'disabled' : ''}`}>
                        <Upload />
                    </label>
                    <input
                        type="file"
                        onChange={handleFileChange}
                        id="file-upload"
                        className="hidden"
                        disabled={fileUploaded}
                    />
                    <button
                        onClick={() => sendMessage()}
                        disabled={isGenerating}
                        className="send-button"
                    >
                        <Send />
                    </button>
                    <button
                        onClick={saveConversation}
                        disabled={!currentConversationId || messages.length === 0}
                        className="save-button"
                    >
                        <Save />
                    </button>
                </div>
                {uploadStatus && <div className="upload-status">{uploadStatus}</div>}
                {saveStatus && <div className="save-status">{saveStatus}</div>}
            </div>
        </div>
    );
});

export default Chat;