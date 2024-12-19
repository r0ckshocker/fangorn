import React from 'react';
import { User, MessageSquare, FileText, Trash2 } from 'lucide-react';
import ConversationNameEditor from './ConversationNameEditor';

const FileIcon = ({ upload, onDeleteItem }) => (
    <div className="file-icon-container" title={upload.original_filename}>
        <FileText className="w-4 h-4 text-gray-400" />
        <div className="file-tooltip">
            <div className="file-info">
                <span className="file-name">{upload.original_filename}</span>
                <span className="file-size">{upload.size}</span>
            </div>
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onDeleteItem(upload, 'upload');
                }}
                className="file-delete-button"
                title="Delete file"
            >
                <Trash2 className="h-3 w-3" />
            </button>
        </div>
    </div>
);

const TreebeardDashboard = ({ 
    dashboardData, 
    loadingConversationId,
    onConversationSelect,
    onDeleteItem,
    onNameUpdate,
    renamingError
}) => {
    if (!dashboardData?.user) return null;

    const conversations = Array.isArray(dashboardData.conversations)
        ? dashboardData.conversations
        : [];
    const { user } = dashboardData;

    return (
        <div className="treebeard-dashboard">
            <div className="user-info">
                <User className="user-icon" />
                <h2>Welcome, {user.name}</h2>
                <span className="conversation-count">
                    {conversations.length}/10 conversations saved
                </span>
            </div>
            <div className="conversations-list">
                {conversations.length >= 10 && (
                    <div className="limit-warning">
                        You've reached the maximum of 10 saved conversations. 
                        Please delete some to create new ones.
                    </div>
                )}
                {renamingError && <p className="error-message">{renamingError}</p>}
                {conversations && conversations.length > 0 ? (
                    <ul className="conversations">
                        {conversations.map((conversation, index) => {
                            if (!conversation) return null;
                            const isLoading = loadingConversationId === conversation.conversation_id;

                            return (
                                <li key={index} className="conversation-item">
                                    <div className="conversation-header">
                                        <div className="conversation-content">
                                            <ConversationNameEditor
                                                conversationId={conversation.conversation_id}
                                                initialName={conversation.name}
                                                onSave={(newName) => onNameUpdate(conversation.conversation_id, newName)}
                                                className="flex-grow"
                                            />
                                        </div>
                                        <div className="conversation-info">
                                            <div className="conversation-files">
                                                <MessageSquare className="w-4 h-4 text-gray-400" />
                                                {conversation.uploads?.map((upload, uploadIndex) => (
                                                    <FileIcon
                                                        key={uploadIndex}
                                                        upload={upload}
                                                        onDeleteItem={onDeleteItem}
                                                    />
                                                ))}
                                            </div>
                                            <span className="conversation-date">
                                                {conversation.last_modified
                                                    ? new Date(conversation.last_modified).toLocaleDateString()
                                                    : 'Unknown date'
                                                }
                                            </span>
                                        </div>
                                    </div>
                                    <div className="conversation-actions">
                                        <button
                                            className={`load-button ${isLoading ? 'loading' : ''}`}
                                            onClick={() => onConversationSelect(conversation.conversation_id)}
                                            disabled={isLoading}
                                        >
                                            {isLoading ? 'Loading...' : 'Load'}
                                        </button>
                                        <button
                                            className="conversation-delete-button"
                                            onClick={() => onDeleteItem(conversation, 'conversation')}
                                            title="Delete conversation"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </button>
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                ) : (
                    <p className="no-conversations">No conversations saved</p>
                )}
            </div>
        </div>
    );
};

export default TreebeardDashboard;