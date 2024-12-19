import React, { useState, useMemo } from 'react';
import { RefreshCw, Link as LinkIcon, ExternalLink, ArrowUpDown, Briefcase, Server, Network, Users } from 'lucide-react';



const getTop3 = (entries) => {
    if (!Array.isArray(entries)) return [];
    return entries
        .sort((a, b) => b[1] - a[1]) // Sort by count descending
        .slice(0, 3) // Take top 3
        .map(([name, count]) => `${name} (${count})`); // Format as "name (count)"
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



const EnvironmentCard = ({ name, env }) => {
    const isHealthy = env.healthz?.toLowerCase() === 'ok' ||
        env.healthz?.toLowerCase() === 'up' ||
        env.healthz?.toLowerCase() === 'healthy';

    const healthClass = isHealthy ? 'text-emerald-400' : 'text-red-400';

    return (
        <div className="env-card">
            <div className="env-card-header">
                <div className="env-name-section">
                    <div className="flex items-center gap-2">
                        <a
                            href={env.healthz_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`env-link ${healthClass}`}
                        >
                            {name}
                            <ExternalLink className="w-3 h-3" />
                        </a>
                    </div>
                </div>
            </div>

            <div className="env-card-content">
                <div className="env-info-grid">
                    <div className="env-info-item">
                        <span className="text-gray-400">Type</span>
                        <span>{env.type || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Level</span>
                        <span>{env.env_level || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Customer</span>
                        <span>{env.customer || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Cluster</span>
                        <span>{env.cluster || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Regions</span>
                        <span>{env.regions?.join(', ') || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Mongo Env</span>
                        <span>{env.mongo_env || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Version</span>
                        <span className="font-mono">{env.package_version || 'N/A'}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Server Start</span>
                        <span>{formatDate(env.server_start_at)}</span>
                    </div>
                    <div className="env-info-item">
                        <span className="text-gray-400">Last Deployed</span>
                        <span>{formatDate(env.deployment_dt)}</span>
                    </div>
                </div>

                {env.projects && (
                    <div className="env-projects">
                        {/* Updated projects display */}
                        {Array.isArray(env.projects) 
                            ? env.projects.map((project, index) => (
                                <span key={index} className="project-item">
                                    {project}
                                </span>
                              ))
                            : Object.keys(env.projects).map((project, index) => (
                                <span key={index} className="project-item">
                                    {project}
                                </span>
                              ))
                        }
                    </div>
                )}

                {env.vanity_urls?.length > 0 && (
                    <div className="env-vanity-urls">
                        <span className="text-gray-400 text-sm mb-1">Vanity URLs</span>
                        <div className="vanity-urls-list">
                            {env.vanity_urls.map(url => {
                                const urlHealth = env.vanity_health?.[url];
                                const isUrlHealthy = urlHealth?.healthz?.toLowerCase() === 'ok' ||
                                    urlHealth?.healthz?.toLowerCase() === 'up' ||
                                    urlHealth?.healthz?.toLowerCase() === 'healthy';
                                return (
                                    <div key={url} className="vanity-url-item">
                                        <LinkIcon
                                            className={`w-3 h-3 ${isUrlHealthy ? 'text-emerald-400' : 'text-red-400'}`}
                                        />
                                        <a
                                            href={urlHealth?.healthz_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className={`vanity-link ${isUrlHealthy ? 'text-emerald-400' : 'text-red-400'}`}
                                        >
                                            {url}
                                        </a>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

const ClusterCard = ({ name, environments }) => {
    const healthyCounts = environments.reduce((acc, env) => {
        const isHealthy = env.healthz?.toLowerCase() === 'ok' ||
            env.healthz?.toLowerCase() === 'up' ||
            env.healthz?.toLowerCase() === 'healthy';
        if (isHealthy) acc.healthy++;
        else acc.unhealthy++;
        return acc;
    }, { healthy: 0, unhealthy: 0 });

    return (
        <div className="info-card">
            <div className="info-card-header">
                <div className="flex items-center gap-2">
                    <Server className="w-5 h-5 text-gray-400" />
                    <h3 className="text-lg font-medium">{name}</h3>
                </div>
                <div className="header-stats">
                    <span className="text-emerald-400">{healthyCounts.healthy} healthy</span>
                    <span className="text-red-400">{healthyCounts.unhealthy} unhealthy</span>
                </div>
            </div>
            <div className="info-card-content">
                <div className="environments-list">
                    {environments.map(env => {
                        const isHealthy = env.healthz?.toLowerCase() === 'ok' ||
                            env.healthz?.toLowerCase() === 'up' ||
                            env.healthz?.toLowerCase() === 'healthy';
                        return (
                            <div key={env.name} className="environment-item">
                                <div className="flex items-center gap-2">
                                    <div className={`status-dot ${isHealthy ? 'bg-emerald-400' : 'bg-red-400'}`} />
                                    <a
                                        href={env.healthz_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="hover:underline"
                                    >
                                        {env.name}
                                    </a>
                                </div>
                                <div className="environment-meta">
                                    <span className="text-gray-400">{env.type}</span>
                                    <span className="text-gray-400">{env.env_level}</span>
                                    <span className="version-tag">{env.package_version || 'no version'}</span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

const CustomerCard = ({ name, environments }) => {
    const stats = environments.reduce((acc, env) => {
        const isHealthy = env.healthz?.toLowerCase() === 'ok' ||
            env.healthz?.toLowerCase() === 'up' ||
            env.healthz?.toLowerCase() === 'healthy';

        if (isHealthy) acc.healthy++;
        else acc.unhealthy++;

        acc.types[env.type] = (acc.types[env.type] || 0) + 1;
        return acc;
    }, { healthy: 0, unhealthy: 0, types: {} });

    return (
        <div className="info-card">
            <div className="info-card-header">
                <div className="flex items-center gap-2">
                    <Briefcase className="w-5 h-5 text-gray-400" />
                    <h3 className="text-lg font-medium">{name}</h3>
                </div>
                <div className="header-stats">
                    <span className="text-emerald-400">{stats.healthy} healthy</span>
                    <span className="text-red-400">{stats.unhealthy} unhealthy</span>
                </div>
            </div>
            <div className="info-card-content">
                <div className="env-types">
                    {Object.entries(stats.types).map(([type, count]) => (
                        <div key={type} className="type-badge">
                            {type}: {count}
                        </div>
                    ))}
                </div>
                <div className="environments-list">
                    {environments.map(env => {
                        const isHealthy = env.healthz?.toLowerCase() === 'ok' ||
                            env.healthz?.toLowerCase() === 'up' ||
                            env.healthz?.toLowerCase() === 'healthy';
                        return (
                            <div key={env.name} className="environment-item">
                                <div className="flex items-center gap-2">
                                    <div className={`status-dot ${isHealthy ? 'bg-emerald-400' : 'bg-red-400'}`} />
                                    <a
                                        href={env.healthz_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="hover:underline"
                                    >
                                        {env.name}
                                    </a>
                                </div>
                                <div className="environment-meta">
                                    <span className="text-gray-400">{env.type}</span>
                                    <span className="text-gray-400">{env.env_level}</span>
                                    {env.vanity_urls?.length > 0 && (
                                        <span className="vanity-count">
                                            <Users className="w-3 h-3" />
                                            {env.vanity_urls.length}
                                        </span>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

const FilterSelect = ({ label, value, onChange, options, placeholder = "All" }) => (
    <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400">{label}</label>
        <select
            value={value}
            onChange={e => onChange(e.target.value)}
            className="search-input text-sm"
        >
            <option value="">{placeholder}</option>
            {options?.map(([key, count]) => (
                <option key={key} value={key}>
                    {key} ({count})
                </option>
            ))}
        </select>
    </div>
);


// const formatDate = (dateString) => {
//     try {
//         if (!dateString || dateString === 'Unknown' || dateString === 'Error' || dateString === 'N/A') {
//             return 'N/A';
//         }

//         // Just return the ISO timestamp as-is
//         if (dateString.includes('T')) {
//             return dateString;
//         }

//         // Only convert if it's a Unix timestamp
//         const unixTimestamp = parseInt(dateString, 10);
//         if (!isNaN(unixTimestamp)) {
//             const date = new Date(unixTimestamp * 1000);
//             return date.toISOString();
//         }

//         return dateString;
//     } catch {
//         return 'Invalid date';
//     }
// };
const formatDate = (dateString) => {
    try {
        if (!dateString || dateString === 'Unknown' || dateString === 'Error' || dateString === 'N/A') {
            return 'N/A';
        }

        // Extract ISO timestamp before the colon if it exists
        const isoMatch = dateString.match(/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z)/);
        if (isoMatch) {
            const date = new Date(isoMatch[1]);
            if (!isNaN(date.getTime())) {
                return date.toLocaleString('en-US', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
            }
        }

        // Unix timestamp
        const unixTimestamp = parseInt(dateString, 10);
        if (!isNaN(unixTimestamp)) {
            const date = new Date(unixTimestamp * 1000);
            if (!isNaN(date.getTime())) {
                return date.toLocaleString('en-US', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
            }
        }

        return 'Invalid date';
    } catch {
        return 'Invalid date';
    }
};

const EnvDashboard = ({ dashboardData, isLoading }) => {
    const [selectedView, setSelectedView] = useState('environments');
    const [filters, setFilters] = useState({
        search: '',
        cluster: '',
        type: '',
        level: '',
        customer: '',
        version: '',
        commit: ''
    });

    const [sortConfig, setSortConfig] = useState({
        key: null,
        direction: 'ascending'
    });



    const stats = useMemo(() => {
        if (!dashboardData?.stats) return null;
        const { clusters = {}, env_types = {}, env_levels = {}, health = {}, customers = {} } = dashboardData.stats;

        const versions = new Map();
        const commits = new Map();
        let totalVanityUrls = 0;
        let healthyVanityUrls = 0;
        let unhealthyVanityUrls = 0;

        Object.values(dashboardData.apps || {}).forEach(env => {
            if (env.package_version) {
                versions.set(env.package_version, (versions.get(env.package_version) || 0) + 1);
            }
            if (env.commit_hash) {
                commits.set(env.commit_hash, (commits.get(env.commit_hash) || 0) + 1);
            }
            if (env.vanity_urls && Array.isArray(env.vanity_urls)) {
                totalVanityUrls += env.vanity_urls.length;
                env.vanity_urls.forEach(url => {
                    const urlHealth = env.vanity_health?.[url];
                    const isUrlHealthy = urlHealth?.healthz?.toLowerCase() === 'ok' ||
                        urlHealth?.healthz?.toLowerCase() === 'up' ||
                        urlHealth?.healthz?.toLowerCase() === 'healthy';
                    if (isUrlHealthy) {
                        healthyVanityUrls++;
                    } else {
                        unhealthyVanityUrls++;
                    }
                });
            }
        });

        return {
            clusters: Object.entries(clusters),
            envTypes: Object.entries(env_types),
            envLevels: Object.entries(env_levels),
            customers: Object.entries(customers),
            versions: Array.from(versions.entries()),
            commits: Array.from(commits.entries()),
            health,
            vanityUrls: {
                total: totalVanityUrls,
                healthy: healthyVanityUrls,
                unhealthy: unhealthyVanityUrls
            }
        };
    }, [dashboardData]);


    const safeIncludes = (value, searchTerm) => {
        if (!searchTerm) return true;
        if (value == null) return false;
        return String(value).toLowerCase().includes(searchTerm.toLowerCase());
    };

    const filteredAndSortedEnvs = useMemo(() => {
        if (!dashboardData?.apps) return [];

        let filteredData = Object.entries(dashboardData.apps)
            .filter(([key, env]) => {
                if (!env.type) return false;
                const vanityMatch = env.vanity_urls?.some(url => safeIncludes(url, filters.search));
                return (safeIncludes(key, filters.search) || vanityMatch) &&
                    (!filters.cluster || env.cluster === filters.cluster) &&
                    (!filters.type || env.type === filters.type) &&
                    (!filters.level || env.env_level === filters.level) &&
                    (!filters.customer || env.customer === filters.customer) &&
                    (!filters.version || env.package_version === filters.version) &&
                    (!filters.commit || safeIncludes(env.commit_hash, filters.commit));
            });

        if (sortConfig.key) {
            filteredData.sort((a, b) => {
                let aValue = a[1][sortConfig.key] || '';
                let bValue = b[1][sortConfig.key] || '';

                // Special handling for the 'name' column which is the key
                if (sortConfig.key === 'name') {
                    aValue = a[0];
                    bValue = b[0];
                }

                // Convert to strings for comparison
                aValue = String(aValue).toLowerCase();
                bValue = String(bValue).toLowerCase();

                if (aValue < bValue) return sortConfig.direction === 'ascending' ? -1 : 1;
                if (aValue > bValue) return sortConfig.direction === 'ascending' ? 1 : -1;
                return 0;
            });
        }

        return filteredData;
    }, [dashboardData, filters, sortConfig]);

    const handleSort = (key) => {
        setSortConfig(prev => ({
            key,
            direction: prev.key === key && prev.direction === 'ascending' ? 'descending' : 'ascending'
        }));
    };

    const healthyCount = filteredAndSortedEnvs.filter(([, env]) =>
        env.healthz?.toLowerCase() === 'ok' ||
        env.healthz?.toLowerCase() === 'up' ||
        env.healthz?.toLowerCase() === 'healthy'
    ).length;


    const clusterData = useMemo(() => {
        const clusters = {};
        filteredAndSortedEnvs.forEach(([name, env]) => {
            const clusterName = env.cluster || 'Unassigned';
            if (!clusters[clusterName]) clusters[clusterName] = [];
            clusters[clusterName].push({ ...env, name });
        });
        return clusters;
    }, [filteredAndSortedEnvs]);

    const customerData = useMemo(() => {
        const customers = {};
        filteredAndSortedEnvs.forEach(([name, env]) => {
            const customerName = env.customer || 'Unassigned';
            if (!customers[customerName]) customers[customerName] = [];
            customers[customerName].push({ ...env, name });
        });
        return customers;
    }, [filteredAndSortedEnvs])

    return (
        <div className="dashboard-content">
            <div className="stats-grid">
        <StatCard
          title="Environments"
          value={filteredAndSortedEnvs.length}
          subValue={[
            { value: `${healthyCount} healthy`, class: 'healthy' },
            { value: `${filteredAndSortedEnvs.length - healthyCount} unhealthy`, class: 'unhealthy' }
          ]}
          icon={Network}
          onClick={() => setSelectedView('environments')}
          isActive={selectedView === 'environments'}
        />
        <StatCard
          title="Vanity URLs"
          value={stats?.vanityUrls.total || 0}
          subValue={[
            { value: `${stats?.vanityUrls.healthy || 0} healthy`, class: 'healthy' },
            { value: `${stats?.vanityUrls.unhealthy || 0} unhealthy`, class: 'unhealthy' }
          ]}
          icon={Users}
        />
        <StatCard
          title="Clusters"
          value={stats?.clusters?.length || 0}
          subValue={getTop3(stats?.clusters)}
          icon={Server}
          onClick={() => setSelectedView('clusters')}
          isActive={selectedView === 'clusters'}
        />
        <StatCard
          title="Customers"
          value={stats?.customers?.length || 0}
          subValue={getTop3(stats?.customers)}
          icon={Briefcase}
          onClick={() => setSelectedView('customers')}
          isActive={selectedView === 'customers'}
        />
      </div>

            <div className="filters-panel">
                <h3 className="text-sm font-medium mb-4">Filters</h3>
                <div className="filters-grid">
                    <div className="flex flex-col gap-1">
                        <label className="text-sm text-gray-400">Search</label>
                        <input
                            type="text"
                            value={filters.search}
                            onChange={e => setFilters(prev => ({ ...prev, search: e.target.value }))}
                            placeholder="Search environments..."
                            className="search-input"
                        />
                    </div>
                    <FilterSelect
                        label="Customer"
                        value={filters.customer}
                        onChange={value => setFilters(prev => ({ ...prev, customer: value }))}
                        options={stats?.customers}
                    />
                    <FilterSelect
                        label="Cluster"
                        value={filters.cluster}
                        onChange={value => setFilters(prev => ({ ...prev, cluster: value }))}
                        options={stats?.clusters}
                    />
                    <FilterSelect
                        label="Type"
                        value={filters.type}
                        onChange={value => setFilters(prev => ({ ...prev, type: value }))}
                        options={stats?.envTypes}
                    />
                    <FilterSelect
                        label="Level"
                        value={filters.level}
                        onChange={value => setFilters(prev => ({ ...prev, level: value }))}
                        options={stats?.envLevels}
                    />
                    <FilterSelect
                        label="Version"
                        value={filters.version}
                        onChange={value => setFilters(prev => ({ ...prev, version: value }))}
                        options={stats?.versions}
                    />
                    <FilterSelect
                        label="Commit"
                        value={filters.commit}
                        onChange={value => setFilters(prev => ({ ...prev, commit: value }))}
                        options={stats?.commits}
                    />
                </div>
            </div>

            {selectedView === 'environments' && (
                <div className="env-grid">
                    {filteredAndSortedEnvs.map(([key, env]) => (
                        <EnvironmentCard key={key} name={key} env={env} />
                    ))}
                </div>
            )}

            {selectedView === 'clusters' && (
                <div className="info-cards-grid">
                    {Object.entries(clusterData).map(([clusterName, environments]) => (
                        <ClusterCard
                            key={clusterName}
                            name={clusterName}
                            environments={environments}
                        />
                    ))}
                </div>
            )}

            {selectedView === 'customers' && (
                <div className="info-cards-grid">
                    {Object.entries(customerData).map(([customerName, environments]) => (
                        <CustomerCard
                            key={customerName}
                            name={customerName}
                            environments={environments}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export default EnvDashboard;