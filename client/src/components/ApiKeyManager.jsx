import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';


const ApiKeyManager = ({ onKeyStatusChange }) => {
    const [apiKey, setApiKey] = useState('');
    const [isKeySet, setIsKeySet] = useState(false);
    const [isChecking, setIsChecking] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [message, setMessage] = useState({ type: '', text: '' });

    useEffect(() => { checkApiKeyStatus(); }, []);

    const checkApiKeyStatus = async () => {
        setIsChecking(true);
        try {
            const res = await fetch(`${API_BASE_URL}/api-key/status`);
            const data = await res.json();
            setIsKeySet(data.is_set);
            if (onKeyStatusChange) onKeyStatusChange(data.is_set);
        } catch (err) { console.error(err); }
        finally { setIsChecking(false); }
    };

    const handleSaveKey = async (e) => {
        e.preventDefault();
        if (!apiKey.trim()) { setMessage({ type: 'error', text: 'Entrez une clé valide.' }); return; }

        setIsSaving(true);
        setMessage({ type: '', text: '' });

        try {
            const res = await fetch('http://localhost:8000/api-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: apiKey }),
            });
            if (res.ok) {
                setMessage({ type: 'success', text: 'Clé enregistrée avec succès' });
                setIsKeySet(true);
                setApiKey('');
                if (onKeyStatusChange) onKeyStatusChange(true);
            } else {
                setMessage({ type: 'error', text: 'Erreur lors de l\'enregistrement' });
            }
        } catch (err) { setMessage({ type: 'error', text: 'Erreur de connexion' }); }
        finally { setIsSaving(false); }
    };

    const handleClearKey = async () => {
        if (!window.confirm("Supprimer la clé API ?")) return;
        await fetch(`${API_BASE_URL}/api-key`, { method: 'DELETE' });
        setIsKeySet(false);
        setMessage({ type: 'info', text: 'Clé supprimée' });
        if (onKeyStatusChange) onKeyStatusChange(false);
    };

    if (isChecking) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-6 border-b border-slate-100 bg-slate-50">
                <h2 className="text-lg font-semibold text-slate-800">Configuration API</h2>
                <p className="text-sm text-slate-500">Gérez la connexion au service d'IA</p>
            </div>

            <div className="p-8 max-w-xl">
                <div className="mb-8 flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-100">
                    <div>
                        <p className="font-medium text-slate-900">État de la connexion</p>
                        <p className="text-sm text-slate-500">Indique si la clé API est configurée</p>
                    </div>
                    {isKeySet ? (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-100 text-emerald-700 text-sm font-medium rounded-full">
                            <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
                            Active
                        </span>
                    ) : (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-100 text-amber-700 text-sm font-medium rounded-full">
                            <span className="w-2 h-2 bg-amber-500 rounded-full"></span>
                            Non configurée
                        </span>
                    )}
                </div>

                <form onSubmit={handleSaveKey} className="space-y-4">
                    <div>
                        <label htmlFor="api-key" className="block text-sm font-medium text-slate-700 mb-1">Clé API Anthropic</label>
                        <input
                            type="password"
                            id="api-key"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            placeholder="sk-ant-api03-..."
                            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition"
                        />
                        <p className="text-xs text-slate-500 mt-2">La clé est stockée localement et n'est jamais partagée.</p>
                    </div>

                    <div className="flex items-center gap-3 pt-2">
                        <button
                            type="submit"
                            disabled={isSaving}
                            className="px-5 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition shadow-sm disabled:opacity-50"
                        >
                            {isSaving ? 'Enregistrement...' : 'Enregistrer'}
                        </button>

                        {isKeySet && (
                            <button
                                type="button"
                                onClick={handleClearKey}
                                className="px-5 py-2 text-slate-600 bg-white border border-slate-300 font-medium rounded-lg hover:bg-slate-50 transition"
                            >
                                Supprimer
                            </button>
                        )}
                    </div>
                </form>

                {message.text && (
                    <div className={`mt-6 p-4 rounded-lg text-sm flex items-center gap-3 ${message.type === 'success' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' :
                        message.type === 'error' ? 'bg-red-50 text-red-700 border border-red-100' :
                            'bg-slate-50 text-slate-700'
                        }`}>
                        {message.text}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ApiKeyManager;
