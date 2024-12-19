// App.jsx
import React, { useState, useCallback, useRef } from 'react';
import Chat from './components/Chat';
import Dashboard from './components/Dashboard';
import ResizablePanel from './components/ResizablePanel';
import './App.css';

function App() {
  const [dashboard, setDashboard] = useState("treebeard");
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const chatRef = useRef(null);

  const handleConversationSelect = useCallback((conversationId) => {
    setCurrentConversationId(conversationId);
  }, []);

  const handleDashboardChange = useCallback((newDashboard) => {
    setDashboard(newDashboard);
    if (chatRef.current) {
      chatRef.current.sendInvisibleMessage(`Switched to ${newDashboard} dashboard`);
    }
  }, []);

  const handleNewChat = useCallback(() => {
    setCurrentConversationId(null);
  }, []);

  const handleUploadSuccess = useCallback(() => {
    handleConversationSelect(currentConversationId);
  }, [currentConversationId, handleConversationSelect]);

  return (
    <div className="app">
      <div className="header">
        <div className="logo">ApprenticeFS</div>
        <div className="nav-buttons">
          <button onClick={() => handleDashboardChange("treebeard")}>Home</button>
          <button onClick={() => handleDashboardChange("env_config")}>Dash</button>
          <button onClick={() => handleDashboardChange("devision")}>Devision</button>
          <button onClick={() => handleDashboardChange("lucius")}>Lucius</button>
          <button 
            onClick={handleNewChat}
            className="new-chat-button"
          >
            New Chat
          </button>
        </div>
      </div>
      <div className="content">
        <ResizablePanel
          isDashboard={dashboard !== "treebeard"}
          leftPanel={
            <Chat 
              ref={chatRef}
              dashboard={dashboard}
              conversationId={currentConversationId}
              onConversationChange={handleConversationSelect}
              onUploadSuccess={handleUploadSuccess}
            />
          }
          rightPanel={
            <Dashboard 
              dashboard={dashboard}
              onConversationSelect={handleConversationSelect}
            />
          }
        />
      </div>
    </div>
  );
}



export default App;