import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Shield, LogOut, Settings, FileText, Cpu, BarChart3, 
  History, TestTube, Save, RefreshCw, Eye, EyeOff,
  Check, X, ChevronDown, ChevronRight, Clock, Zap,
  AlertTriangle, Info, Edit3, Copy, Trash2
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// ============ LOGIN COMPONENT ============
function AdminLogin({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      const data = await response.json();

      if (data.success) {
        localStorage.setItem('admin_token', data.token);
        localStorage.setItem('admin_email', data.admin_email);
        onLogin(data.token);
      } else {
        setError(data.detail || 'Login failed');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-violet-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-violet-500 to-fuchsia-500 rounded-xl flex items-center justify-center">
              <Shield className="w-7 h-7 text-white" />
            </div>
            <span className="text-2xl font-bold text-white">RIGHTNAME</span>
          </div>
          <h1 className="text-xl text-violet-200">Admin Panel</h1>
        </div>

        {/* Login Form */}
        <div className="bg-white/10 backdrop-blur-xl rounded-2xl p-8 border border-white/20">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-violet-200 mb-2">
                Admin Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500"
                placeholder="admin@example.com"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-violet-200 mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500 pr-12"
                  placeholder="••••••••"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/60 hover:text-white"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-200 text-sm flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-semibold rounded-xl hover:from-violet-500 hover:to-fuchsia-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  Authenticating...
                </>
              ) : (
                <>
                  <Shield className="w-5 h-5" />
                  Access Admin Panel
                </>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-white/40 text-sm mt-6">
          Secure admin access only. All actions are logged.
        </p>
      </div>
    </div>
  );
}

// ============ MAIN ADMIN DASHBOARD ============
function AdminDashboard({ token, onLogout }) {
  const [activeTab, setActiveTab] = useState('evaluations');
  const [loading, setLoading] = useState(false);

  const tabs = [
    { id: 'evaluations', label: 'Evaluations', icon: BarChart3 },
    { id: 'prompts', label: 'System Prompts', icon: FileText },
    { id: 'models', label: 'Model Settings', icon: Cpu },
    { id: 'analytics', label: 'Usage Analytics', icon: BarChart3 },
    { id: 'history', label: 'Prompt History', icon: History },
    { id: 'test', label: 'Test Mode', icon: TestTube },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-violet-500 to-fuchsia-500 rounded-xl flex items-center justify-center">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-800">RIGHTNAME Admin</h1>
              <p className="text-xs text-slate-500">{localStorage.getItem('admin_email')}</p>
            </div>
          </div>
          
          <button
            onClick={onLogout}
            className="flex items-center gap-2 px-4 py-2 text-slate-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <LogOut className="w-5 h-5" />
            Logout
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Tab Navigation */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-violet-600 text-white shadow-lg shadow-violet-200'
                  : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
              }`}
            >
              <tab.icon className="w-5 h-5" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
          {activeTab === 'evaluations' && <EvaluationsTab token={token} />}
          {activeTab === 'prompts' && <PromptsTab token={token} />}
          {activeTab === 'models' && <ModelsTab token={token} />}
          {activeTab === 'analytics' && <AnalyticsTab token={token} />}
          {activeTab === 'history' && <HistoryTab token={token} />}
          {activeTab === 'test' && <TestTab token={token} />}
        </div>
      </div>
    </div>
  );
}

// ============ PROMPTS TAB ============
function PromptsTab({ token }) {
  const [promptType, setPromptType] = useState('system');
  const [prompt, setPrompt] = useState('');
  const [originalPrompt, setOriginalPrompt] = useState('');
  const [promptName, setPromptName] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [promptInfo, setPromptInfo] = useState(null);

  const fetchPrompt = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/prompts/${promptType}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setPrompt(data.content || '');
      setOriginalPrompt(data.content || '');
      setPromptInfo(data);
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to load prompt' });
    } finally {
      setLoading(false);
    }
  }, [promptType, token]);

  useEffect(() => {
    fetchPrompt();
  }, [fetchPrompt]);

  const savePrompt = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/prompts/${promptType}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          prompt_type: promptType,
          content: prompt,
          name: promptName || undefined
        })
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: 'Prompt saved successfully!' });
        setOriginalPrompt(prompt);
        setPromptName('');
        fetchPrompt();
      } else {
        setMessage({ type: 'error', text: 'Failed to save prompt' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Connection error' });
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = prompt !== originalPrompt;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800">System Prompts</h2>
          <p className="text-slate-500 text-sm mt-1">Edit the prompts sent to the LLM</p>
        </div>
        
        {/* Prompt Type Selector */}
        <div className="flex gap-2">
          <button
            onClick={() => setPromptType('system')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              promptType === 'system'
                ? 'bg-violet-100 text-violet-700 border-2 border-violet-300'
                : 'bg-slate-100 text-slate-600 border-2 border-transparent hover:bg-slate-200'
            }`}
          >
            Main System Prompt
          </button>
          <button
            onClick={() => setPromptType('early_stopping')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              promptType === 'early_stopping'
                ? 'bg-violet-100 text-violet-700 border-2 border-violet-300'
                : 'bg-slate-100 text-slate-600 border-2 border-transparent hover:bg-slate-200'
            }`}
          >
            Early Stopping Prompt
          </button>
        </div>
      </div>

      {/* Prompt Info */}
      {promptInfo && (
        <div className="mb-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate-500">
              <strong>Version:</strong> {promptInfo.name || 'Default'}
            </span>
            {promptInfo.last_modified && (
              <span className="text-slate-500">
                <strong>Modified:</strong> {new Date(promptInfo.last_modified).toLocaleString()}
              </span>
            )}
            {promptInfo.is_default && (
              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                Default
              </span>
            )}
            <span className="text-slate-500">
              <strong>Characters:</strong> {prompt.length.toLocaleString()}
            </span>
          </div>
        </div>
      )}

      {/* Editor */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="w-8 h-8 text-violet-500 animate-spin" />
        </div>
      ) : (
        <>
          <div className="relative">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="w-full h-[500px] p-4 font-mono text-sm bg-slate-900 text-green-400 rounded-xl border border-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
              placeholder="Enter your prompt here..."
            />
            
            {hasChanges && (
              <div className="absolute top-3 right-3 px-2 py-1 bg-amber-500 text-white text-xs font-medium rounded">
                Unsaved Changes
              </div>
            )}
          </div>

          {/* Save Section */}
          <div className="mt-4 flex items-center gap-4">
            <input
              type="text"
              value={promptName}
              onChange={(e) => setPromptName(e.target.value)}
              placeholder="Version name (optional)"
              className="flex-1 max-w-xs px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
            />
            
            <button
              onClick={savePrompt}
              disabled={!hasChanges || saving}
              className="flex items-center gap-2 px-6 py-2 bg-violet-600 text-white font-medium rounded-lg hover:bg-violet-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-5 h-5" />
                  Save Prompt
                </>
              )}
            </button>

            <button
              onClick={() => setPrompt(originalPrompt)}
              disabled={!hasChanges}
              className="flex items-center gap-2 px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
            >
              <X className="w-5 h-5" />
              Discard
            </button>
          </div>

          {/* Message */}
          {message && (
            <div className={`mt-4 p-3 rounded-lg flex items-center gap-2 ${
              message.type === 'success' 
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
              {message.type === 'success' ? <Check className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
              {message.text}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ============ MODELS TAB ============
function ModelsTab({ token }) {
  const [settings, setSettings] = useState({
    primary_model: 'gpt-4o-mini',
    fallback_models: ['claude-sonnet-4-20250514', 'gpt-4o'],
    timeout_seconds: 35,
    temperature: 0.7,
    max_tokens: 8000,
    retry_count: 2
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const availableModels = [
    { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'OpenAI', speed: 'Fast', cost: 'Low' },
    { id: 'gpt-4o', name: 'GPT-4o', provider: 'OpenAI', speed: 'Medium', cost: 'Medium' },
    { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4', provider: 'Anthropic', speed: 'Medium', cost: 'Medium' },
    { id: 'gpt-4.1', name: 'GPT-4.1', provider: 'OpenAI', speed: 'Slow', cost: 'High' },
  ];

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/settings/model`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setSettings(data);
    } catch (err) {
      console.error('Failed to fetch settings');
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/settings/model`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: 'Settings saved successfully!' });
      } else {
        setMessage({ type: 'error', text: 'Failed to save settings' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Connection error' });
    } finally {
      setSaving(false);
    }
  };

  const toggleFallbackModel = (modelId) => {
    const current = settings.fallback_models || [];
    if (current.includes(modelId)) {
      setSettings({ ...settings, fallback_models: current.filter(m => m !== modelId) });
    } else {
      setSettings({ ...settings, fallback_models: [...current, modelId] });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="w-8 h-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-800">Model Settings</h2>
        <p className="text-slate-500 text-sm mt-1">Configure LLM models and parameters</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Primary Model */}
        <div className="p-5 bg-slate-50 rounded-xl border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-500" />
            Primary Model
          </h3>
          <select
            value={settings.primary_model}
            onChange={(e) => setSettings({ ...settings, primary_model: e.target.value })}
            className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {availableModels.map(model => (
              <option key={model.id} value={model.id}>
                {model.name} ({model.provider}) - {model.speed}, {model.cost} cost
              </option>
            ))}
          </select>
        </div>

        {/* Fallback Models */}
        <div className="p-5 bg-slate-50 rounded-xl border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-blue-500" />
            Fallback Models (in order)
          </h3>
          <div className="space-y-2">
            {availableModels.filter(m => m.id !== settings.primary_model).map(model => (
              <label key={model.id} className="flex items-center gap-3 p-3 bg-white rounded-lg border border-slate-200 cursor-pointer hover:border-violet-300">
                <input
                  type="checkbox"
                  checked={(settings.fallback_models || []).includes(model.id)}
                  onChange={() => toggleFallbackModel(model.id)}
                  className="w-5 h-5 text-violet-600 rounded focus:ring-violet-500"
                />
                <span className="flex-1">{model.name}</span>
                <span className="text-xs text-slate-500">{model.provider}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Timeout */}
        <div className="p-5 bg-slate-50 rounded-xl border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-orange-500" />
            Timeout (seconds)
          </h3>
          <input
            type="range"
            min="10"
            max="120"
            value={settings.timeout_seconds}
            onChange={(e) => setSettings({ ...settings, timeout_seconds: parseInt(e.target.value) })}
            className="w-full"
          />
          <div className="flex justify-between mt-2 text-sm text-slate-500">
            <span>10s</span>
            <span className="font-semibold text-violet-600">{settings.timeout_seconds}s</span>
            <span>120s</span>
          </div>
        </div>

        {/* Temperature */}
        <div className="p-5 bg-slate-50 rounded-xl border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Settings className="w-5 h-5 text-red-500" />
            Temperature (Creativity)
          </h3>
          <input
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={settings.temperature}
            onChange={(e) => setSettings({ ...settings, temperature: parseFloat(e.target.value) })}
            className="w-full"
          />
          <div className="flex justify-between mt-2 text-sm text-slate-500">
            <span>0 (Deterministic)</span>
            <span className="font-semibold text-violet-600">{settings.temperature}</span>
            <span>2 (Creative)</span>
          </div>
        </div>

        {/* Max Tokens */}
        <div className="p-5 bg-slate-50 rounded-xl border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-4">Max Tokens</h3>
          <input
            type="number"
            min="1000"
            max="32000"
            value={settings.max_tokens}
            onChange={(e) => setSettings({ ...settings, max_tokens: parseInt(e.target.value) })}
            className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
          />
          <p className="text-xs text-slate-500 mt-2">Controls maximum response length (1,000 - 32,000)</p>
        </div>

        {/* Retry Count */}
        <div className="p-5 bg-slate-50 rounded-xl border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-4">Retry Count per Model</h3>
          <select
            value={settings.retry_count}
            onChange={(e) => setSettings({ ...settings, retry_count: parseInt(e.target.value) })}
            className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {[1, 2, 3, 4, 5].map(n => (
              <option key={n} value={n}>{n} {n === 1 ? 'retry' : 'retries'}</option>
            ))}
          </select>
          <p className="text-xs text-slate-500 mt-2">Number of retries before switching to fallback</p>
        </div>
      </div>

      {/* Save Button */}
      <div className="mt-6 flex items-center gap-4">
        <button
          onClick={saveSettings}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-3 bg-violet-600 text-white font-medium rounded-lg hover:bg-violet-700 transition-colors disabled:opacity-50"
        >
          {saving ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
          Save Settings
        </button>
        
        {message && (
          <div className={`p-3 rounded-lg flex items-center gap-2 ${
            message.type === 'success' 
              ? 'bg-green-50 text-green-700'
              : 'bg-red-50 text-red-700'
          }`}>
            {message.type === 'success' ? <Check className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
            {message.text}
          </div>
        )}
      </div>
    </div>
  );
}

// ============ ANALYTICS TAB ============
function AnalyticsTab({ token }) {
  const [stats, setStats] = useState(null);
  const [recentEvals, setRecentEvals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  useEffect(() => {
    fetchAnalytics();
  }, [days]);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const [statsRes, recentRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/admin/analytics/usage?days=${days}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch(`${BACKEND_URL}/api/admin/analytics/recent?limit=10`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);
      
      const statsData = await statsRes.json();
      const recentData = await recentRes.json();
      
      setStats(statsData);
      setRecentEvals(recentData.evaluations || []);
    } catch (err) {
      console.error('Failed to fetch analytics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="w-8 h-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Usage Analytics</h2>
          <p className="text-slate-500 text-sm mt-1">Monitor API usage and performance</p>
        </div>
        
        <select
          value={days}
          onChange={(e) => setDays(parseInt(e.target.value))}
          className="px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
        >
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
        </select>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="p-5 bg-gradient-to-br from-violet-500 to-violet-600 rounded-xl text-white">
          <p className="text-violet-200 text-sm">Total Evaluations</p>
          <p className="text-3xl font-bold mt-1">{stats?.total_evaluations || 0}</p>
        </div>
        <div className="p-5 bg-gradient-to-br from-green-500 to-green-600 rounded-xl text-white">
          <p className="text-green-200 text-sm">Successful</p>
          <p className="text-3xl font-bold mt-1">{stats?.successful_evaluations || 0}</p>
        </div>
        <div className="p-5 bg-gradient-to-br from-red-500 to-red-600 rounded-xl text-white">
          <p className="text-red-200 text-sm">Failed</p>
          <p className="text-3xl font-bold mt-1">{stats?.failed_evaluations || 0}</p>
        </div>
        <div className="p-5 bg-gradient-to-br from-amber-500 to-amber-600 rounded-xl text-white">
          <p className="text-amber-200 text-sm">Avg Response Time</p>
          <p className="text-3xl font-bold mt-1">{stats?.average_response_time || 0}s</p>
        </div>
      </div>

      {/* Model Usage */}
      {stats?.model_usage && Object.keys(stats.model_usage).length > 0 && (
        <div className="mb-8">
          <h3 className="font-semibold text-slate-800 mb-4">Model Usage</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(stats.model_usage).map(([model, count]) => (
              <div key={model} className="p-4 bg-slate-50 rounded-xl border border-slate-200">
                <p className="text-xs text-slate-500 truncate">{model}</p>
                <p className="text-2xl font-bold text-slate-800">{count}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Evaluations */}
      <div>
        <h3 className="font-semibold text-slate-800 mb-4">Recent Evaluations</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">Brand</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">Category</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">Verdict</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">Score</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">Time</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">Model</th>
              </tr>
            </thead>
            <tbody>
              {recentEvals.map((eval_, idx) => (
                <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-3 px-4 font-medium text-slate-800">
                    {eval_.brand_names?.join(', ') || 'N/A'}
                  </td>
                  <td className="py-3 px-4 text-slate-600">{eval_.category || 'N/A'}</td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      eval_.verdict === 'GO' ? 'bg-green-100 text-green-700' :
                      eval_.verdict === 'REJECT' ? 'bg-red-100 text-red-700' :
                      'bg-amber-100 text-amber-700'
                    }`}>
                      {eval_.verdict || 'N/A'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-600">{eval_.score || 'N/A'}</td>
                  <td className="py-3 px-4 text-slate-600">{eval_.processing_time ? `${eval_.processing_time.toFixed(1)}s` : 'N/A'}</td>
                  <td className="py-3 px-4 text-slate-500 text-xs">{eval_.model_used || 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ============ HISTORY TAB ============
function HistoryTab({ token }) {
  const [promptType, setPromptType] = useState('system');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [restoring, setRestoring] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, [promptType]);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/prompts/${promptType}/history`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setHistory(data.history || []);
    } catch (err) {
      console.error('Failed to fetch history');
    } finally {
      setLoading(false);
    }
  };

  const restoreVersion = async (versionName) => {
    setRestoring(versionName);
    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/prompts/${promptType}/restore/${encodeURIComponent(versionName)}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        fetchHistory();
      }
    } catch (err) {
      console.error('Failed to restore version');
    } finally {
      setRestoring(null);
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Prompt History</h2>
          <p className="text-slate-500 text-sm mt-1">View and restore previous prompt versions</p>
        </div>
        
        <div className="flex gap-2">
          <button
            onClick={() => setPromptType('system')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              promptType === 'system'
                ? 'bg-violet-100 text-violet-700'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            System Prompt
          </button>
          <button
            onClick={() => setPromptType('early_stopping')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              promptType === 'early_stopping'
                ? 'bg-violet-100 text-violet-700'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Early Stopping
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="w-8 h-8 text-violet-500 animate-spin" />
        </div>
      ) : history.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <History className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No version history yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((version, idx) => (
            <div
              key={idx}
              className={`p-4 rounded-xl border ${
                version.is_active
                  ? 'bg-violet-50 border-violet-200'
                  : 'bg-white border-slate-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-medium text-slate-800">{version.name}</h4>
                    {version.is_active && (
                      <span className="px-2 py-0.5 bg-violet-500 text-white text-xs rounded-full">
                        Active
                      </span>
                    )}
                    {version.is_default && (
                      <span className="px-2 py-0.5 bg-blue-500 text-white text-xs rounded-full">
                        Default
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-slate-500 mt-1">
                    {version.created_at ? new Date(version.created_at).toLocaleString() : 'N/A'}
                    {version.created_by && ` • by ${version.created_by}`}
                  </p>
                </div>
                
                {!version.is_active && (
                  <button
                    onClick={() => restoreVersion(version.name)}
                    disabled={restoring === version.name}
                    className="flex items-center gap-2 px-4 py-2 bg-violet-100 text-violet-700 rounded-lg hover:bg-violet-200 transition-colors disabled:opacity-50"
                  >
                    {restoring === version.name ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <RefreshCw className="w-4 h-4" />
                    )}
                    Restore
                  </button>
                )}
              </div>
              
              <div className="mt-3 p-3 bg-slate-900 rounded-lg">
                <pre className="text-xs text-green-400 overflow-hidden whitespace-pre-wrap max-h-32">
                  {version.content?.substring(0, 500)}
                  {version.content?.length > 500 && '...'}
                </pre>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============ TEST TAB ============
function TestTab({ token }) {
  const [promptType, setPromptType] = useState('system');
  const [testInput, setTestInput] = useState(JSON.stringify({
    brand_name: 'TestBrand',
    category: 'Technology',
    industry: 'SaaS'
  }, null, 2));
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const runTest = async () => {
    setLoading(true);
    try {
      let parsedInput;
      try {
        parsedInput = JSON.parse(testInput);
      } catch {
        setResult({ error: 'Invalid JSON input' });
        setLoading(false);
        return;
      }

      const response = await fetch(`${BACKEND_URL}/api/admin/test/prompt`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          prompt_type: promptType,
          test_input: parsedInput
        })
      });
      
      const data = await response.json();
      setResult(data);
    } catch (err) {
      setResult({ error: 'Test failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-800">Test Mode</h2>
        <p className="text-slate-500 text-sm mt-1">Preview prompts without making actual LLM calls</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <h3 className="font-semibold text-slate-800">Test Input</h3>
            <select
              value={promptType}
              onChange={(e) => setPromptType(e.target.value)}
              className="px-3 py-1 border border-slate-300 rounded-lg text-sm"
            >
              <option value="system">System Prompt</option>
              <option value="early_stopping">Early Stopping</option>
            </select>
          </div>
          
          <textarea
            value={testInput}
            onChange={(e) => setTestInput(e.target.value)}
            className="w-full h-64 p-4 font-mono text-sm bg-slate-900 text-green-400 rounded-xl border border-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
            placeholder='{"brand_name": "Test", "category": "Tech"}'
          />
          
          <button
            onClick={runTest}
            disabled={loading}
            className="mt-4 flex items-center gap-2 px-6 py-3 bg-violet-600 text-white font-medium rounded-lg hover:bg-violet-700 transition-colors disabled:opacity-50"
          >
            {loading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <TestTube className="w-5 h-5" />}
            Run Test
          </button>
        </div>

        {/* Output */}
        <div>
          <h3 className="font-semibold text-slate-800 mb-4">Preview Result</h3>
          
          {result ? (
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              {result.error ? (
                <div className="text-red-600">{result.error}</div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-500">Prompt Type:</span>
                    <span className="font-medium">{result.prompt_type}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-500">Prompt Length:</span>
                    <span className="font-medium">{result.prompt_length?.toLocaleString()} chars</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-500">Est. Tokens:</span>
                    <span className="font-medium">~{Math.round(result.estimated_tokens || 0)}</span>
                  </div>
                  
                  <div className="mt-4">
                    <p className="text-sm text-slate-500 mb-2">Prompt Preview:</p>
                    <pre className="p-3 bg-slate-900 text-green-400 rounded-lg text-xs overflow-auto max-h-64 whitespace-pre-wrap">
                      {result.prompt_preview}
                    </pre>
                  </div>
                  
                  <div className="p-3 bg-blue-50 text-blue-700 rounded-lg text-sm flex items-center gap-2">
                    <Info className="w-5 h-5" />
                    {result.note}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-8 bg-slate-50 rounded-xl border border-slate-200 text-center text-slate-500">
              <TestTube className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>Run a test to see the prompt preview</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============ MAIN COMPONENT ============
export default function AdminPanel() {
  const [token, setToken] = useState(localStorage.getItem('admin_token'));
  const [verifying, setVerifying] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    verifyToken();
  }, []);

  const verifyToken = async () => {
    if (!token) {
      setVerifying(false);
      return;
    }

    try {
      const response = await fetch(`${BACKEND_URL}/api/admin/verify`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (!response.ok) {
        localStorage.removeItem('admin_token');
        localStorage.removeItem('admin_email');
        setToken(null);
      }
    } catch (err) {
      console.error('Token verification failed');
    } finally {
      setVerifying(false);
    }
  };

  const handleLogin = (newToken) => {
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_email');
    setToken(null);
  };

  if (verifying) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <RefreshCw className="w-8 h-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  if (!token) {
    return <AdminLogin onLogin={handleLogin} />;
  }

  return <AdminDashboard token={token} onLogout={handleLogout} />;
}
