import React, { useState, useMemo } from 'react';
import {
  Shield, AlertTriangle, Code, Key, Package, 
  Clock, Filter, Server, Network, Link as LinkIcon,
  ExternalLink, Calendar
} from 'lucide-react';

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

const RuleCard = ({ rule, stats, alerts }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="info-card">
      <div className="info-card-header">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-gray-400" />
          <h3 className="text-lg font-medium">{rule}</h3>
        </div>
        <div className="header-stats">
          {Object.entries(stats.severity_counts || {}).map(([severity, count]) => (
            <span key={severity} className={`text-${severity === 'critical' ? 'red' : severity === 'high' ? 'orange' : severity === 'medium' ? 'yellow' : 'blue'}-400`}>
              {severity} ({count})
            </span>
          ))}
        </div>
      </div>
      <div className="info-card-content">
        <div className="environments-list">
          {alerts.map(alert => (
            <div key={alert.id} className="environment-item">
              <div className="flex items-center gap-2">
                <div className={`status-dot ${alert.severity === 'critical' ? 'bg-red-400' : 
                  alert.severity === 'high' ? 'bg-orange-400' : 
                  alert.severity === 'medium' ? 'bg-yellow-400' : 
                  'bg-blue-400'}`} />
                <span className="text-gray-300">{alert.description}</span>
              </div>
              <div className="environment-meta">
                <span className="text-gray-400">{alert.path}</span>
                <span className="version-tag">{alert.age_days}d old</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const AppCard = ({ name, alerts }) => {
  const alertStats = useMemo(() => {
    return alerts.reduce((acc, alert) => {
      acc.total++;
      acc.severity[alert.severity] = (acc.severity[alert.severity] || 0) + 1;
      return acc;
    }, { total: 0, severity: {} });
  }, [alerts]);

  return (
    <div className="info-card">
      <div className="info-card-header">
        <div className="flex items-center gap-2">
          <Server className="w-5 h-5 text-gray-400" />
          <h3 className="text-lg font-medium">{name}</h3>
        </div>
        <div className="header-stats">
          {Object.entries(alertStats.severity).map(([severity, count]) => (
            <span key={severity} className={`text-${
              severity === 'critical' ? 'red' : 
              severity === 'high' ? 'orange' : 
              severity === 'medium' ? 'yellow' : 
              'blue'}-400`}>
              {severity} ({count})
            </span>
          ))}
        </div>
      </div>
      <div className="info-card-content">
        <div className="environments-list">
          {alerts.map(alert => (
            <div key={alert.id} className="environment-item">
              <div className="flex items-center gap-2">
                <div className={`status-dot ${
                  alert.severity === 'critical' ? 'bg-red-400' : 
                  alert.severity === 'high' ? 'bg-orange-400' : 
                  alert.severity === 'medium' ? 'bg-yellow-400' : 
                  'bg-blue-400'}`} />
                <span className="text-gray-300">{alert.rule}</span>
              </div>
              <div className="environment-meta">
                <span className="text-gray-400">{alert.description}</span>
                <span className="version-tag">{alert.age_days}d old</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const AgeDistributionCard = ({ stats }) => {
  const ageRanges = {
    "2d": stats["2"] || 0,
    "7d": stats["7"] || 0,
    "30d": stats["30"] || 0,
    "60d": stats["60"] || 0,
    "90d": stats["90"] || 0,
    "90d+": stats["100"] || 0
  };

  return (
    <div className="info-card">
      <div className="info-card-header">
        <div className="flex items-center gap-2">
          <Calendar className="w-5 h-5 text-gray-400" />
          <h3 className="text-lg font-medium">Age Distribution</h3>
        </div>
      </div>
      <div className="p-4">
        <div className="grid grid-cols-6 gap-2">
          {Object.entries(ageRanges).map(([range, count]) => (
            <div key={range} className="flex flex-col items-center">
              <div className="text-2xl font-bold text-gray-200">{count}</div>
              <div className="text-sm text-gray-400">{range}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const LuciusDashboard = ({ dashboardData, isLoading }) => {
  const [selectedView, setSelectedView] = useState('rules');
  const [filters, setFilters] = useState({
    search: '',
    severity: '',
    rule: '',
    app: '',
    showDismissed: false
  });

  // Process stats and alerts
  const stats = useMemo(() => {
    if (!dashboardData?.stats) return null;
    
    return {
      rules: Object.entries(dashboardData.apps?.rule_stats || {}),
      apps: Object.entries(dashboardData.apps?.alerts || {})
        .reduce((acc, [_, alert]) => {
          if (!filters.showDismissed && alert.state === 'dismissed') return acc;
          const appName = alert.app_name;
          if (!acc[appName]) acc[appName] = [];
          acc[appName].push(alert);
          return acc;
        }, {}),
      age_distribution: dashboardData.stats.age_distribution || {},
      type_counts: dashboardData.stats.type_counts || {}
    };
  }, [dashboardData, filters.showDismissed]);

  // Filter alerts
  const processedAlerts = useMemo(() => {
    if (!dashboardData?.apps?.alerts) return [];
    
    return Object.values(dashboardData.apps.alerts)
      .filter(alert => {
        if (!filters.showDismissed && alert.state === 'dismissed') return false;
        
        const searchMatch = !filters.search || 
          alert.description?.toLowerCase().includes(filters.search.toLowerCase()) ||
          alert.path?.toLowerCase().includes(filters.search.toLowerCase());
          
        const severityMatch = !filters.severity || 
          alert.severity.toLowerCase() === filters.severity.toLowerCase();
          
        const ruleMatch = !filters.rule || alert.rule === filters.rule;
        const appMatch = !filters.app || alert.app_name === filters.app;
        
        return searchMatch && severityMatch && ruleMatch && appMatch;
      });
  }, [dashboardData, filters]);

  const openAlerts = processedAlerts.filter(alert => alert.state === 'open');
  const criticalAlerts = processedAlerts.filter(alert => 
    alert.severity.toLowerCase() === 'critical' || 
    alert.severity.toLowerCase() === 'high'
  );

  if (isLoading) {
    return <div className="flex justify-center items-center h-full">
      <Shield className="w-8 h-8 animate-spin text-blue-500" />
    </div>;
  }

  return (
    <div className="dashboard-content">
      {/* Stats Overview */}
      <div className="stats-grid">
        <StatCard
          title="Open Alerts"
          value={openAlerts.length}
          subValue={[
            { value: `${criticalAlerts.length} critical`, class: 'text-red-400' },
            { value: `${openAlerts.length - criticalAlerts.length} other`, class: 'text-gray-400' }
          ]}
          icon={AlertTriangle}
          onClick={() => setSelectedView('rules')}
          isActive={selectedView === 'rules'}
        />
        <StatCard
          title="Code Scanning"
          value={stats?.type_counts?.code_scanning || 0}
          subValue={getTop3(stats?.rules)}
          icon={Code}
        />
        <StatCard
          title="Applications"
          value={Object.keys(stats?.apps || {}).length}
          subValue={getTop3(Object.entries(stats?.apps || {}).map(([name, alerts]) => 
            [name, alerts.length]))}
          icon={Server}
          onClick={() => setSelectedView('apps')}
          isActive={selectedView === 'apps'}
        />
        <StatCard
          title="Age Distribution"
          value={`${stats?.age_distribution['7'] || 0} < 7d`}
          subValue={getTop3(Object.entries(stats?.age_distribution || {}))}
          icon={Calendar}
          onClick={() => setSelectedView('age')}
          isActive={selectedView === 'age'}
        />
      </div>

            {/* Filters */}
      <div className="filters-panel">
        <h3 className="text-sm font-medium mb-4">Filters</h3>
        <div className="filters-grid">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">Search</label>
            <input
              type="text"
              value={filters.search}
              onChange={e => setFilters(prev => ({ ...prev, search: e.target.value }))}
              placeholder="Search alerts..."
              className="search-input text-sm"
            />
          </div>
          
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">Severity</label>
            <select
              value={filters.severity}
              onChange={e => setFilters(prev => ({ ...prev, severity: e.target.value }))}
              className="search-input text-sm"
            >
              <option value="">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">Rule</label>
            <select
              value={filters.rule}
              onChange={e => setFilters(prev => ({ ...prev, rule: e.target.value }))}
              className="search-input text-sm"
            >
              <option value="">All Rules</option>
              {Object.keys(dashboardData?.apps?.rule_stats || {}).map(rule => (
                <option key={rule} value={rule}>{rule}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-400">Application</label>
            <select
              value={filters.app}
              onChange={e => setFilters(prev => ({ ...prev, app: e.target.value }))}
              className="search-input text-sm"
            >
              <option value="">All Applications</option>
              {Object.keys(stats?.apps || {}).map(app => (
                <option key={app} value={app}>{app}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2 mt-6">
            <input
              type="checkbox"
              id="showDismissed"
              checked={filters.showDismissed}
              onChange={e => setFilters(prev => ({ ...prev, showDismissed: e.target.checked }))}
              className="rounded bg-gray-700 border-gray-600"
            />
            <label htmlFor="showDismissed" className="text-sm text-gray-400">
              Show dismissed alerts
            </label>
          </div>
        </div>
      </div>

      {/* View-specific content */}
      <div className="mt-6">
        {selectedView === 'rules' && (
          <div className="info-cards-grid">
            {Object.entries(dashboardData.apps?.rule_stats || {})
              .filter(([rule, _]) => !filters.rule || rule === filters.rule)
              .map(([rule, stats]) => {
                const ruleAlerts = processedAlerts.filter(alert => alert.rule === rule);
                return (
                  <RuleCard
                    key={rule}
                    rule={rule === 'dependency_alerts' ? 'Dependencies' :
                          rule === 'secret_scanning_alerts' ? 'Secret Scanning' :
                          rule}
                    stats={stats}
                    alerts={ruleAlerts}
                  />
                );
              })}
          </div>
        )}

        {selectedView === 'apps' && (
          <div className="info-cards-grid">
            {Object.entries(stats?.apps || {})
              .filter(([app, _]) => !filters.app || app === filters.app)
              .map(([app, alerts]) => (
                <AppCard
                  key={app}
                  name={app}
                  alerts={alerts}
                />
              ))}
          </div>
        )}

        {selectedView === 'age' && (
          <div className="space-y-6">
            <AgeDistributionCard stats={stats.age_distribution} />
            <div className="info-cards-grid">
              {[
                ['Recent (<7d)', alert => alert.age_days <= 7],
                ['This Month (<30d)', alert => alert.age_days <= 30 && alert.age_days > 7],
                ['Aging (30-90d)', alert => alert.age_days > 30 && alert.age_days <= 90],
                ['Old (>90d)', alert => alert.age_days > 90]
              ].map(([label, filterFn]) => {
                const filteredAlerts = processedAlerts.filter(filterFn);
                if (filteredAlerts.length === 0) return null;
                
                return (
                  <div key={label} className="info-card">
                    <div className="info-card-header">
                      <div className="flex items-center gap-2">
                        <Clock className="w-5 h-5 text-gray-400" />
                        <h3 className="text-lg font-medium">{label}</h3>
                      </div>
                      <div className="text-sm text-gray-400">
                        {filteredAlerts.length} alerts
                      </div>
                    </div>
                    <div className="info-card-content">
                      <div className="environments-list">
                        {filteredAlerts.map(alert => (
                          <div key={alert.id} className="environment-item">
                            <div className="flex items-center gap-2">
                              <div className={`status-dot ${
                                alert.severity === 'critical' ? 'bg-red-400' : 
                                alert.severity === 'high' ? 'bg-orange-400' : 
                                alert.severity === 'medium' ? 'bg-yellow-400' : 
                                'bg-blue-400'}`} />
                              <span className="text-gray-300">{alert.description}</span>
                            </div>
                            <div className="environment-meta">
                              <span className="text-gray-400">{alert.path}</span>
                              <span className="version-tag">{alert.age_days}d old</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              }).filter(Boolean)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LuciusDashboard;