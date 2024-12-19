import React, { useState, useEffect } from 'react';
import { Edit2, Check, X } from 'lucide-react';
import '../styles/ConversationNameEditor.css'; // Add this import

const ConversationNameEditor = ({ 
  conversationId, 
  initialName, 
  onSave,
  className = '' 
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(initialName || '');
  const [tempName, setTempName] = useState(name);

  useEffect(() => {
    setName(initialName || '');
    setTempName(initialName || '');
  }, [initialName]);

  const handleSave = async () => {
    const trimmedName = tempName.trim();
    if (trimmedName && trimmedName !== name) {
      try {
        await onSave(trimmedName);
        setName(trimmedName);
      } catch (error) {
        console.error('Error saving name:', error);
        setTempName(name);
      }
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setTempName(name);
    setIsEditing(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (isEditing) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <input
          type="text"
          value={tempName}
          onChange={(e) => setTempName(e.target.value)}
          onKeyDown={handleKeyPress}
          className="name-editor-input"
          autoFocus
          placeholder={conversationId}
          maxLength={50}
        />
        <button 
          onClick={handleSave}
          className="name-editor-button"
          title="Save"
        >
          <Check className="h-4 w-4 text-green-400" />
        </button>
        <button 
          onClick={handleCancel}
          className="name-editor-button"
          title="Cancel"
        >
          <X className="h-4 w-4 text-red-400" />
        </button>
      </div>
    );
  }

  return (
    <div className={`name-editor-container flex items-center gap-2 group ${className}`}>
      <span 
        className="name-display"
        title={name || conversationId}
      >
        {name || conversationId}
      </span>
      <button 
        onClick={() => setIsEditing(true)}
        className="name-edit-button"
        title="Edit name"
      >
        <Edit2 className="h-4 w-4 text-blue-400" />
      </button>
    </div>
  );
};

export default ConversationNameEditor;