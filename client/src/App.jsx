import React, { useState, useEffect } from 'react';
import SourceManager from './components/SourceManager';
import SheetViewer from './components/SheetViewer';
import ApiKeyManager from './components/ApiKeyManager';
import DissertationGenerator from './components/DissertationGenerator';
import Revisions from './components/Revisions';
import LoginPage from './components/LoginPage';
import { API_BASE_URL } from './config';

function App() {
  const [activeTab, setActiveTab] = useState('sources');
  const [isApiKeySet, setIsApiKeySet] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(null); // null = loading, false = not auth, true = auth
  const [user, setUser] = useState(null);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      checkApiKey();
    }
  }, [isAuthenticated]);

  const getAuthHeaders = () => {
    const token = localStorage.getItem('eps_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  };

  const checkAuth = async () => {
    const token = localStorage.getItem('eps_token');
    if (!token) {
      setIsAuthenticated(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: getAuthHeaders()
      });

      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
        setIsAuthenticated(true);
      } else {
        localStorage.removeItem('eps_token');
        setIsAuthenticated(false);
      }
    } catch (err) {
      console.error('Auth check failed:', err);
      setIsAuthenticated(false);
    }
  };

  const checkApiKey = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api-key/status`);
      const data = await res.json();
      setIsApiKeySet(data.is_set);
    } catch (err) {
      setIsApiKeySet(false);
    }
  };

  const handleLoginSuccess = (token) => {
    localStorage.setItem('eps_token', token);
    checkAuth();
  };

  const handleLogout = () => {
    localStorage.removeItem('eps_token');
    setIsAuthenticated(false);
    setUser(null);
  };

  const handleKeyStatusChange = (isSet) => {
    setIsApiKeySet(isSet);
  };

  // Loading state
  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 bg-slate-900 rounded-2xl flex items-center justify-center text-white font-bold text-2xl mx-auto mb-4 shadow-lg animate-pulse">
            E1
          </div>
          <p className="text-slate-500 font-medium">Chargement...</p>
        </div>
      </div>
    );
  }

  // Not authenticated - show login page
  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  const tabs = [
    { id: 'sources', label: 'Sources' },
    { id: 'sheets', label: 'Fiches' },
    { id: 'revisions', label: 'Revisions' },
    { id: 'dissertation', label: 'Dissertation' },
    { id: 'apikey', label: 'Reglages' },
  ];

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user || !user.email) return '??';
    return user.email.substring(0, 2).toUpperCase();
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header - Clean & Minimal */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">

          {/* Logo / Brand - Keeping "Ecrit 1" */}
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-slate-900 rounded-xl flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-slate-200">
              E1
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 leading-none">Ecrit 1</h1>
              <p className="text-xs text-slate-500 font-medium tracking-wide">Histoire de l'EPS</p>
            </div>
          </div>

          {/* Navigation - Pill Style */}
          <nav className="flex bg-slate-100 p-1.5 rounded-full gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-6 py-2 text-sm font-bold rounded-full transition-all duration-200 ${activeTab === tab.id
                  ? 'bg-white text-slate-900 shadow-sm transform scale-105'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
                  }`}
              >
                {tab.label}
                {tab.id === 'apikey' && isApiKeySet === false && (
                  <span className="ml-2 w-1.5 h-1.5 inline-block bg-amber-500 rounded-full animate-pulse"></span>
                )}
              </button>
            ))}
          </nav>

          {/* Right Section - Profile / Status */}
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-bold border border-emerald-100">
              <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
              OBJECTIF CAPEPS
            </div>

            {/* User Menu */}
            <div className="relative group">
              <div className="w-10 h-10 bg-slate-100 rounded-full border border-slate-200 flex items-center justify-center text-slate-600 font-bold hover:bg-slate-200 cursor-pointer transition-colors">
                {getUserInitials()}
              </div>

              {/* Dropdown */}
              <div className="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                <div className="px-4 py-2 border-b border-slate-100">
                  <p className="text-xs text-slate-500">Connecte en tant que</p>
                  <p className="text-sm font-bold text-slate-900 truncate">{user?.email}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2 text-left text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
                >
                  Se deconnecter
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* API Key Warning */}
        {isApiKeySet === false && activeTab !== 'apikey' && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
                <svg className="w-4 h-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                </svg>
              </div>
              <p className="text-amber-900 text-sm font-medium">
                Configuration requise : Ajoutez votre cle API pour commencer l'analyse.
              </p>
            </div>
            <button
              onClick={() => setActiveTab('apikey')}
              className="px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 transition shadow-sm"
            >
              Configurer
            </button>
          </div>
        )}

        {/* Tab Components */}
        <div className="animate-fadeIn">

          {/* Persist components using CSS visibility to keep state alive */}
          <div style={{ display: activeTab === 'sources' ? 'block' : 'none' }}>
            <div className="max-w-4xl mx-auto">
              <SourceManager isApiKeySet={isApiKeySet} />
            </div>
          </div>

          <div style={{ display: activeTab === 'sheets' ? 'block' : 'none' }}>
            <SheetViewer />
          </div>

          <div style={{ display: activeTab === 'dissertation' ? 'block' : 'none' }}>
            <DissertationGenerator />
          </div>

          <div style={{ display: activeTab === 'revisions' ? 'block' : 'none' }}>
            <Revisions />
          </div>

          <div style={{ display: activeTab === 'apikey' ? 'block' : 'none' }}>
            <div className="max-w-2xl mx-auto py-12">
              <ApiKeyManager onKeyStatusChange={handleKeyStatusChange} />
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}

export default App;
