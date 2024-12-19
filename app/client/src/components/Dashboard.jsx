import React, { useEffect, useState, useCallback } from 'react';
import axios from '../axiosSetup';
import Modal from 'react-modal';
import { RefreshCw } from 'lucide-react';
import '../styles/Dashboard.css';
import EnvDashboard from './EnvDashboard';
import TreebeardDashboard from './TreebeardDashboard';
import LuciusDashboard from './LuciusDashboard';
import DevisionDashboard from './DevisionDashboard';



// Bind modal to your appElement
Modal.setAppElement('#root');

function Dashboard({ dashboard, onConversationSelect }) {
  const [dashboardData, setDashboardData] = useState(null);
  const [refreshing, setRefreshing] = useState(true);
  const [error, setError] = useState(null);
  const [loadingConversationId, setLoadingConversationId] = useState(null);
  const [modalIsOpen, setModalIsOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null);
  const [deleteType, setDeleteType] = useState(null);
  const [renamingError, setRenamingError] = useState(null);

  const fetchData = useCallback(async (dashboard_id) => {
    try {
      setRefreshing(true);
      const response = await axios.get(`/dash?dashboard_id=${dashboard_id}`);
      setDashboardData(response.data);
      setError(null);
    } catch (error) {
      console.error('Error fetching data:', error);
      setError('Error fetching data. Please try again later.');
      setDashboardData(null);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setDashboardData(null);
    setError(null);
    fetchData(dashboard);
  }, [dashboard, fetchData]);

  const refreshData = useCallback(async () => {
    try {
      setError('Invoking Lambda Function...');
      const response = await axios.get(`/dash?dashboard_id=${dashboard}&action=refresh`);
      if (response.status === 200) {
        setError(null);
        await fetchData(dashboard);
      }
    } catch (error) {
      setError('Failed to refresh dashboard');
      console.error('Refresh error:', error);
    }
  }, [dashboard, fetchData]);

  const handleConversationSelect = useCallback(async (conversation_id) => {
    if (!conversation_id || loadingConversationId) return;
  
    setLoadingConversationId(conversation_id);
    try {
      const response = await axios.get(
        `/chat?action=get_conversation&dashboard_id=${dashboard}&conversation_id=${conversation_id}`
      );
      if (onConversationSelect) {
        onConversationSelect(conversation_id);
      }
    } catch (error) {
      console.error('Error loading conversation:', error);
      setError('Failed to load conversation');
      onConversationSelect(null);
    } finally {
      setLoadingConversationId(null);
    }
  }, [dashboard, onConversationSelect]);

  const handleNameUpdate = async (conversationId, newName) => {
    try {
      setRenamingError(null);
      const response = await axios.post('/chat', {
        action: 'update_name',
        conversation_id: conversationId,
        name: newName,
        dashboard_id: dashboard
      });

      if (response.data.status === 'success') {
        await fetchData(dashboard);
        return true;
      } else {
        throw new Error(response.data.error || 'Failed to update name');
      }
    } catch (error) {
      setRenamingError('Failed to update conversation name');
      console.error('Error updating conversation name:', error);
      throw error;
    }
  };

  const handleDelete = async () => {
    if (!itemToDelete) return;

    try {
      const response = await axios.post('/chat', {
        action: deleteType === 'conversation' ? 'delete_conversation' : 'delete_upload',
        conversation_id: deleteType === 'conversation'
          ? itemToDelete.conversation_id
          : itemToDelete.key.split('/')[1],
        upload_key: deleteType === 'upload' ? itemToDelete.key : undefined,
        dashboard_id: dashboard
      });

      if (response.data.status === 'success') {
        fetchData(dashboard);
        setModalIsOpen(false);
        setItemToDelete(null);
        setDeleteType(null);
        
        if (deleteType === 'conversation' && itemToDelete.conversation_id === loadingConversationId) {
          onConversationSelect(null);
        }
      }
    } catch (error) {
      console.error('Error deleting item:', error);
      setError('Failed to delete item. Please try again.');
    }
  };

  const handleDeleteItem = (item, type) => {
    setItemToDelete(item);
    setDeleteType(type);
    setModalIsOpen(true);
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>
          {dashboard === 'env_config' && 'Dash'}
          {dashboard === 'devision' && 'Devision'}
          {dashboard === 'lucius' && 'Lucius'}
          {dashboard === 'treebeard' && 'treebeard V2'}
        </h1>
        <h2>Presented by ITSEC</h2>
      </header>

      <div className="dashboard-controls">
        <div className="refresh-info">
          <span>Last Updated: {dashboardData?.updated ? new Date(dashboardData.updated).toLocaleString() : 'Never'}</span>
          <button onClick={refreshData} className="refresh-button" disabled={refreshing}>
            <RefreshCw className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {refreshing ? (
        <div className="loading">Loading...</div>
      ) : dashboardData ? (
        <>
          {dashboard === 'treebeard' && (
            <>
              <TreebeardDashboard
                dashboardData={dashboardData}
                loadingConversationId={loadingConversationId}
                onConversationSelect={handleConversationSelect}
                onDeleteItem={handleDeleteItem}
                onNameUpdate={handleNameUpdate}
                renamingError={renamingError}
              />
              <Modal
                isOpen={modalIsOpen}
                onRequestClose={() => setModalIsOpen(false)}
                className="delete-modal"
                overlayClassName="delete-modal-overlay"
                contentLabel="Delete Confirmation"
                ariaHideApp={false}
              >
                <h2>Confirm Deletion</h2>
                <p>
                  {deleteType === 'conversation'
                    ? 'This will delete the conversation and all its associated uploads. This action cannot be undone.'
                    : 'This will delete the selected upload and its analysis. This action cannot be undone.'}
                </p>
                <div className="modal-buttons">
                  <button onClick={() => setModalIsOpen(false)}>Cancel</button>
                  <button onClick={handleDelete} className="delete-confirm">Delete</button>
                </div>
              </Modal>
            </>
          )}
          {dashboard === 'env_config' && (
            <EnvDashboard 
              dashboardData={dashboardData}
              isLoading={refreshing}
            />
          )}
          {dashboard === 'lucius' && (
            <LuciusDashboard
              dashboardData={dashboardData}
              isLoading={refreshing}
            />
          )}
          {dashboard === 'devision' && (
            <DevisionDashboard
              dashboardData={dashboardData}
              isLoading={refreshing}
            />
          )}
        </>
      ) : (
        <p className="no-data">No data available</p>
      )}
    </div>
  );
}

export default Dashboard;