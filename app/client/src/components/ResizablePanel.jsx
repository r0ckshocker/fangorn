import React, { useState, useEffect, useCallback } from 'react';
import { GripVertical } from 'lucide-react';

const ResizablePanel = ({ 
  leftPanel, 
  rightPanel, 
  isDashboard = false 
}) => {
  // Set initial width based on dashboard type
  const [leftWidth, setLeftWidth] = useState(isDashboard ? 25 : 50);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = React.useRef(null);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleMouseMove = useCallback((e) => {
    if (!isDragging || !containerRef.current) return;

    const containerRect = containerRef.current.getBoundingClientRect();
    const containerWidth = containerRect.width;
    const mouseX = e.clientX - containerRect.left;
    const percentage = (mouseX / containerWidth) * 100;

    // Constrain between 20% and 80%
    const newWidth = Math.min(Math.max(percentage, 20), 80);
    setLeftWidth(newWidth);
  }, [isDragging]);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    } else {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // Update width when dashboard changes
  useEffect(() => {
    setLeftWidth(isDashboard ? 25 : 50);
  }, [isDashboard]);

  return (
    <div ref={containerRef} className="resize-panel-container">
      <div style={{ width: `${leftWidth}%` }} className="h-full overflow-hidden">
        {leftPanel}
      </div>
      <div
        className={`resize-divider ${isDragging ? 'dragging' : ''}`}
        onMouseDown={handleMouseDown}
      >
        <GripVertical className="w-4 h-4 text-gray-400" />
      </div>
      <div style={{ width: `calc(${100 - leftWidth}% - 6px)` }} className="h-full overflow-hidden">
        {rightPanel}
      </div>
    </div>
  );
};

export default ResizablePanel;