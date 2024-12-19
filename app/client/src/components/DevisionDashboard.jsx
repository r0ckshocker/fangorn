import React, { useState, useMemo } from 'react';
import { Laptop, Battery, Shield, Clock, Network, RefreshCw, Users, Briefcase } from 'lucide-react';

const getTop3 = (entries) => {
    if (!Array.isArray(entries)) return [];
    return entries
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([name, count]) => `${name} (${count})`);
};

const StatCard = ({ title, value, subValue, icon: Icon, onClick, isActive = false }) => (
    <div 
        className={`stat-card ${isActive ? 'ring-2 ring-blue-500' : ''} cursor-pointer hover:bg-gray-800 transition-all`}
        onClick={onClick}
    >
        <div className="stat-header">
            <h3 className="text-sm font-medium text-gray-400">{title}</h3>
            {Icon && <Icon className={`w-5 h-5 ${isActive ? 'text-blue-500' : 'text-gray-400'}`} />}
        </div>
        <div className="stat-content">
            <div className="stat-value">{value}</div>
            {subValue && (
                Array.isArray(subValue) ? (
                    subValue[0]?.class ? (
                        <div className="stat-subvalue">
                            {subValue.map((item, index) => (
                                <span key={index} className={`stat-subvalue-item ${item.class}`}>
                                    {item.value}
                                </span>
                            ))}
                        </div>
                    ) : (
                        <div className="stat-subvalue-list">
                            {subValue.map((item, index) => (
                                <div key={index} className="stat-subvalue-list-item">
                                    {item}
                                </div>
                            ))}
                        </div>
                    )
                ) : (
                    <div className="stat-subvalue">{subValue}</div>
                )
            )}
        </div>
    </div>
);

const DeviceCard = ({ serial, device }) => {
    const lastSeen = new Date(device.last_seen_kandji);
    const isRecent = new Date() - lastSeen < 24 * 60 * 60 * 1000;
    const healthClass = isRecent ? 'text-emerald-400' : 'text-red-400';

    return (
        <div className="env-card">
            <div className="env-card-header">
                <div className="env-name-section">
                    <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                            <span className={healthClass}>●</span>
                            <span className="font-medium">{device.device_name || serial}</span>
                        </div>
                        <span className="text-sm text-gray-400">{device.model_kandji}</span>
                    </div>
                </div>
            </div>

            <div className="env-card-content">
                <div className="env-info-grid">
                    <div className="env-info-item">
                        <span className="text-gray-400">User</span>
                        <span className="flex items-center gap-1">
                            <Users className="w-4 h-4" />
                            {device.user_kandji || 'N/A'}
                        </span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">OS Version</span>
                        <span>{device.os_version || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Blueprint</span>
                        <span>{device.blueprint || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">MDM Status</span>
                        <span className={device.mdm_status === 'enabled' ? 'text-emerald-400' : 'text-red-400'}>
                            <Shield className="w-4 h-4 inline mr-1" />
                            {device.mdm_status}
                        </span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">API URL</span>
                        <span>{device.api_url || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Last Active</span>
                        <span>
                            <Clock className="w-4 h-4 inline mr-1" />
                            {lastSeen.toLocaleString()}
                        </span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">IP Address</span>
                        <span>
                            <Network className="w-4 h-4 inline mr-1" />
                            {device.ip_address || 'N/A'}
                        </span>
                    </div>
                    
                    {device.battery_percentage && (
                        <div className="env-info-item col-span-2">
                            <span className="text-gray-400">Battery Health</span>
                            <div className="flex items-center gap-2">
                                <Battery className="w-4 h-4" />
                                <span>{device.battery_percentage}% ({device.battery_cycle_count} cycles)</span>
                            </div>
                        </div>
                    )}
                </div>

                {device.warranty && (
                    <div className="mt-2 p-2 rounded bg-gray-800">
                        <div className="text-sm">
                            <span className="text-gray-400">Warranty:</span>
                            <span className={`ml-2 ${device.warranty.status === 'active' ? 'text-emerald-400' : 'text-red-400'}`}>
                                {device.warranty.status}
                            </span>
                            {device.warranty.expires && (
                                <span className="ml-2 text-gray-400">
                                    (Expires: {new Date(device.warranty.expires).toLocaleDateString()})
                                </span>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

const ModelCard = ({ modelName, devices }) => {
    const stats = devices.reduce((acc, device) => {
        const isActive = new Date() - new Date(device.last_seen_kandji) < 24 * 60 * 60 * 1000;
        if (isActive) acc.active++;
        return acc;
    }, { active: 0, total: devices.length });

    return (
        <div className="info-card">
            <div className="info-card-header">
                <div className="flex items-center gap-2">
                    <Laptop className="w-5 h-5 text-gray-400" />
                    <h3 className="text-lg font-medium">{modelName}</h3>
                </div>
                <div className="header-stats">
                    <span className="text-emerald-400">{stats.active} active</span>
                    <span className="text-gray-400">{stats.total} total</span>
                </div>
            </div>
            <div className="info-card-content">
                <div className="environments-list">
                    {devices.map(device => (
                        <div key={device.serial} className="environment-item">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className={`status-dot ${
                                        new Date() - new Date(device.last_seen_kandji) < 24 * 60 * 60 * 1000 
                                        ? 'bg-emerald-400' : 'bg-red-400'
                                    }`} />
                                    <span>{device.device_name || device.serial}</span>
                                </div>
                                <span className="text-sm text-gray-400">{device.user_kandji}</span>
                            </div>
                            <div className="environment-meta">
                                <span className="text-gray-400">{device.os_version}</span>
                                <span className="text-gray-400">{device.blueprint}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

const DevisionDashboard = ({ dashboardData, isLoading }) => {
    const [selectedView, setSelectedView] = useState('devices');
    const [filters, setFilters] = useState({
        search: '',
        model: '',
        os: '',
        blueprint: '',
        status: ''
    });

    const stats = useMemo(() => {
        if (!dashboardData?.stats) return null;
        return dashboardData.stats;
    }, [dashboardData]);

    const filteredDevices = useMemo(() => {
        if (!dashboardData?.apps) return [];

        return Object.entries(dashboardData.apps)
            .filter(([serial, device]) => {
                if (!device) return false;
                const searchLower = filters.search.toLowerCase();
                return (
                    (device.device_name?.toLowerCase().includes(searchLower) ||
                     device.serial?.toLowerCase().includes(searchLower) ||
                     device.user_kandji?.toLowerCase().includes(searchLower)) &&
                    (!filters.model || device.model_kandji === filters.model) &&
                    (!filters.os || device.os_version === filters.os) &&
                    (!filters.blueprint || device.blueprint === filters.blueprint) &&
                    (!filters.status || device.mdm_status === filters.status)
                );
            });
    }, [dashboardData, filters]);

    const devicesByModel = useMemo(() => {
        const models = {};
        filteredDevices.forEach(([serial, device]) => {
            const model = device.model_kandji || 'Unknown';
            if (!models[model]) models[model] = [];
            models[model].push({ ...device, serial });
        });
        return models;
    }, [filteredDevices]);

    const FilterSelect = ({ label, value, onChange, options, placeholder = "All" }) => (
        <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">{label}</label>
            <select
                value={value}
                onChange={e => onChange(e.target.value)}
                className="search-input text-sm"
            >
                <option value="">{placeholder}</option>
                {Object.entries(options || {}).map(([key, count]) => (
                    <option key={key} value={key}>
                        {key} ({count})
                    </option>
                ))}
            </select>
        </div>
    );

    return (
        <div className="dashboard-content">
            <div className="stats-grid">
                <StatCard
                    title="Total Devices"
                    value={filteredDevices.length}
                    subValue={[
                        { value: `${stats?.mdm_status?.enabled || 0} MDM Active`, class: 'healthy' },
                        { value: `${stats?.mdm_status?.disabled || 0} MDM Inactive`, class: 'unhealthy' }
                    ]}
                    icon={Laptop}
                    onClick={() => setSelectedView('devices')}
                    isActive={selectedView === 'devices'}
                />
                <StatCard
                    title="Device Activity"
                    value={stats?.last_seen?.today || 0}
                    subValue={[
                        { value: `${stats?.last_seen?.week || 0} this week`, class: 'text-blue-400' },
                        { value: `${stats?.last_seen?.older || 0} inactive`, class: 'unhealthy' }
                    ]}
                    icon={Clock}
                />
                <StatCard
                    title="Models"
                    value={Object.keys(stats?.models || {}).length}
                    subValue={getTop3(Object.entries(stats?.models || {}))}
                    icon={Briefcase}
                    onClick={() => setSelectedView('models')}
                    isActive={selectedView === 'models'}
                />
                <StatCard
                    title="OS Versions"
                    value={Object.keys(stats?.os_versions || {}).length}
                    subValue={getTop3(Object.entries(stats?.os_versions || {}))}
                    icon={Shield}
                />
            </div>

            <div className="filters-panel">
                <div className="filters-grid">
                    <div className="flex flex-col gap-1">
                        <label className="text-xs text-gray-400">Search</label>
                        <input
                            type="text"
                            value={filters.search}
                            onChange={e => setFilters(prev => ({ ...prev, search: e.target.value }))}
                            placeholder="Search devices..."
                            className="search-input"
                        />
                    </div>
                    <FilterSelect
                        label="Model"
                        value={filters.model}
                        onChange={value => setFilters(prev => ({ ...prev, model: value }))}
                        options={stats?.models}
                    />
                    <FilterSelect
                        label="OS Version"
                        value={filters.os}
                        onChange={value => setFilters(prev => ({ ...prev, os: value }))}
                        options={stats?.os_versions}
                    />
                    <FilterSelect
                        label="Blueprint"
                        value={filters.blueprint}
                        onChange={value => setFilters(prev => ({ ...prev, blueprint: value }))}
                        options={stats?.blueprints}
                    />
                </div>
            </div>

            {selectedView === 'devices' && (
                <div className="env-grid">
                    {filteredDevices.map(([serial, device]) => (
                        <DeviceCard key={serial} serial={serial} device={device} />
                    ))}
                </div>
            )}

            {selectedView === 'models' && (
                <div className="info-cards-grid">
                    {Object.entries(devicesByModel).map(([modelName, devices]) => (
                        <ModelCard
                            key={modelName}
                            modelName={modelName}
                            devices={devices}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export default DevisionDashboard;