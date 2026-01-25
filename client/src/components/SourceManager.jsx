import React, { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '../config';

import DefinitionManager from './DefinitionManager';

const SourceManager = ({ isApiKeySet }) => {
    const [sources, setSources] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState({ currentFile: 0, totalFiles: 0, currentFileName: '' });
    const [elapsedTime, setElapsedTime] = useState(0);
    const timerRef = useRef(null);
    const [abortController, setAbortController] = useState(null);
    const [refreshing, setRefreshing] = useState(false); // Global refresh state

    useEffect(() => { fetchSources(); }, []);

    useEffect(() => {
        if (uploading) {
            timerRef.current = setInterval(() => setElapsedTime(prev => prev + 1), 1000);
        } else {
            if (timerRef.current) clearInterval(timerRef.current);
        }
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [uploading]);

    const fetchSources = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/sources`);
            setSources(await res.json());
        } catch (err) { console.error("Failed to fetch sources", err); }
    };

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const [activeJobs, setActiveJobs] = useState({}); // { jobId: { processingState... } }

    // Polling effect for active jobs
    // Polling effect for active jobs
    useEffect(() => {
        // Initial fetch of active jobs to restore state
        const fetchActiveJobs = async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/jobs/active`);
                if (res.ok) {
                    const jobs = await res.json();
                    if (Object.keys(jobs).length > 0) {
                        setActiveJobs(jobs);
                    }
                }
            } catch (e) { console.error("Error fetching active jobs", e); }
        };
        fetchActiveJobs();

        const checkJobs = async () => {
            const jobsToCheck = Object.keys(activeJobs);
            if (jobsToCheck.length === 0) return;

            for (const jobId of jobsToCheck) {
                try {
                    const res = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
                    const data = await res.json();

                    if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled' || data.status === 'not_found' || data.progress === 100) {
                        // Job done, remove from tracking and refresh sources
                        setActiveJobs(prev => {
                            const newState = { ...prev };
                            delete newState[jobId];
                            return newState;
                        });
                        await fetchSources();
                    } else {
                        // Update status
                        setActiveJobs(prev => ({
                            ...prev,
                            [jobId]: { ...prev[jobId], ...data }
                        }));
                    }
                } catch (e) {
                    console.error("Polling error", e);
                }
            }
        };

        const interval = setInterval(checkJobs, 3000); // Poll every 3s for performance
        return () => clearInterval(interval);
    }, [activeJobs]);

    // Initial fetch of sources on mount
    useEffect(() => {
        fetchSources();
    }, []);

    const handleUpload = async (e) => {
        const files = Array.from(e.target.files);
        if (files.length === 0) return;
        if (isApiKeySet === false) { alert("Configurez votre cle API."); return; }

        setUploading(true);
        setElapsedTime(0);
        setProgress({ currentFile: 0, totalFiles: files.length, currentFileName: files[0]?.name || '' });

        const controller = new AbortController();
        setAbortController(controller);
        const duplicates = [];

        try {
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                setProgress(prev => ({ ...prev, currentFile: i + 1, currentFileName: file.name }));

                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch(`${API_BASE_URL}/upload`, {
                    method: 'POST', body: formData, signal: controller.signal
                });
                const data = await response.json();

                if (data.status === 'duplicate') {
                    duplicates.push(data.filename);
                } else if (data.job_id) {
                    // Start tracking job
                    setActiveJobs(prev => ({
                        ...prev,
                        [data.job_id]: {
                            job_id: data.job_id,
                            filename: data.filename,
                            status: 'pending',
                            progress: '0/0',
                            message: 'En attente...'
                        }
                    }));
                }
            }
            // fetchSources(); // We don't fetch immediately, the job poller will do it when done
            if (duplicates.length > 0) alert(`Doublons : ${duplicates.join(', ')}`);
        } catch (err) {
            if (err.name !== 'AbortError') console.error("Upload failed", err);
        } finally {
            setUploading(false);
            e.target.value = null;
            setAbortController(null);
        }
    };

    const handleCancel = (e) => { e.preventDefault(); abortController?.abort(); };

    const handleRetry = async (id, e) => {
        e.stopPropagation();
        try {
            const res = await fetch(`${API_BASE_URL}/sources/${id}/retry`, { method: 'POST' });
            const data = await res.json();

            if (data.job_id) {
                setActiveJobs(prev => ({
                    ...prev,
                    [data.job_id]: {
                        job_id: data.job_id,
                        filename: "Relance...", // Will be updated by polling
                        status: 'pending',
                        progress: 0,
                        message: 'En attente (Retry)...'
                    }
                }));
                // Optionally trigger a fetch to see updated status immediately (like removing the red error temporarily?)
                // Actually the polling will handle it.
                fetchSources();
            }
        } catch (err) { console.error("Retry failed", err); }
    };

    const handleDelete = async (id, e) => {
        e.stopPropagation();
        try {
            await fetch(`${API_BASE_URL}/sources/${id}`, { method: 'DELETE' });
            fetchSources();
        } catch (err) { console.error(err); }
    };

    const handleCancelJob = async (jobId) => {
        try {
            await fetch(`${API_BASE_URL}/jobs/${jobId}/cancel`, { method: 'POST' });
            // Remove from active jobs immediately for responsive UI
            setActiveJobs(prev => {
                const newState = { ...prev };
                delete newState[jobId];
                return newState;
            });
        } catch (err) { console.error("Cancel failed", err); }
    };

    const handleRefreshAll = async () => {
        if (!window.confirm("Voulez-vous relancer l'analyse complète de TOUTES les sources ?\n\nCela effacera les analyses actuelles pour les recréer avec les dernières consignes de l'IA (notamment les Nuances).\nCela peut prendre plusieurs minutes.")) return;

        setRefreshing(true);
        try {
            const res = await fetch(`${API_BASE_URL}/refresh-analysis`, { method: 'POST' });
            const data = await res.json();

            if (data.jobs && data.jobs.length > 0) {
                // Add new jobs to activeJobs tracking
                // We need to fetch active jobs again properly to merge, or manually add them
                // The endpoint returns [{job_id, filename}, ...]
                // Let's manually construct the state to be responsive immediately

                const newJobsState = {};
                data.jobs.forEach(job => {
                    newJobsState[job.job_id] = {
                        job_id: job.job_id,
                        filename: job.filename,
                        status: 'pending',
                        progress: 0,
                        message: 'Actualisation démarrée...'
                    };
                });

                setActiveJobs(prev => ({ ...prev, ...newJobsState }));

                // Force a sources refresh to show "not analyzed" state if needed, though activeJobs handles the UI
                fetchSources();
            } else {
                setRefreshing(false);
                alert("Aucune source à actualiser.");
            }
        } catch (err) {
            console.error("Refresh failed", err);
            alert("Erreur lors du lancement de l'actualisation");
        } finally {
            setRefreshing(false);
        }
    };

    const progressPercent = progress.totalFiles > 0 ? (progress.currentFile / progress.totalFiles) * 100 : 0;

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* Header Section */}
            <div>
                <h2 className="text-3xl font-bold text-slate-900 leading-tight">Sources & Documents</h2>
                <p className="text-slate-500 mt-2 text-lg">Gérez votre base de connaissances pour l'analyse historique.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Left Column: Knowledge Base (Fiches) */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 flex flex-col h-full">
                    <div className="flex items-center gap-4 mb-8">
                        <div className="w-12 h-12 bg-slate-900 rounded-xl flex items-center justify-center text-white shadow-lg shadow-slate-200">
                            <span className="font-bold text-xl">1</span>
                        </div>
                        <div>
                            <h3 className="text-xl font-bold text-slate-900">Sources Historiques</h3>
                            <p className="text-sm text-slate-500">Fiches, Cours & Articles</p>
                        </div>
                    </div>

                    {/* Upload Zone */}
                    <div className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer group ${uploading
                        ? 'border-indigo-300 bg-indigo-50/50'
                        : 'border-slate-200 hover:border-slate-400 hover:bg-slate-50'
                        }`}>
                        <input type="file" accept="application/pdf" multiple onChange={handleUpload} className="hidden" id="pdf-upload" disabled={uploading} />
                        <label htmlFor="pdf-upload" className="block cursor-pointer">
                            {uploading ? (
                                <div className="space-y-4">
                                    <div className="w-12 h-12 border-3 border-slate-200 border-t-slate-900 rounded-full animate-spin mx-auto"></div>
                                    <div>
                                        <p className="font-bold text-slate-900">Analyse en cours...</p>
                                        <p className="text-sm text-slate-500">{progress.currentFileName}</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    <div className="w-12 h-12 bg-slate-100 text-slate-600 rounded-xl flex items-center justify-center mx-auto transition-colors group-hover:bg-slate-200 group-hover:text-slate-900">
                                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" /></svg>
                                    </div>
                                    <div>
                                        <p className="font-bold text-slate-900">Ajouter des documents</p>
                                        <p className="text-sm text-slate-500">PDF uniquement</p>
                                    </div>
                                </div>
                            )}
                        </label>
                    </div>
                </div>

                {/* Right Column: Definitions (Placeholder Wrapper) */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 h-full">
                    <div className="flex items-center gap-4 mb-8">
                        <div className="w-12 h-12 bg-slate-900 rounded-xl flex items-center justify-center text-white shadow-lg shadow-slate-200">
                            <span className="font-bold text-xl">2</span>
                        </div>
                        <div>
                            <h3 className="text-xl font-bold text-slate-900">Définitions</h3>
                            <p className="text-sm text-slate-500">Concepts & Citations Clés</p>
                        </div>
                    </div>
                    {/* We let DefinitionManager handle its internal logic, but we might hide its header via css if needed. */}
                    <DefinitionManager />
                </div>
            </div>

            {/* List Section - Full Width */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                    <h3 className="font-bold text-slate-900">Documents Analysés ({sources.length})</h3>
                    {sources.length > 0 && (
                        <button
                            onClick={handleRefreshAll}
                            disabled={refreshing || Object.keys(activeJobs).length > 0}
                            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all border flex items-center gap-2 ${refreshing
                                ? 'bg-slate-100 text-slate-400 border-transparent cursor-not-allowed'
                                : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50 hover:border-slate-300 shadow-sm'
                                }`}
                        >
                            <svg className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                            Mettre à jour l'IA
                        </button>
                    )}
                </div>

                {/* Processing Jobs */}
                {Object.keys(activeJobs).length > 0 && (
                    <div className="p-6 border-b border-slate-100 bg-indigo-50/30 space-y-3">
                        {Object.values(activeJobs).map(job => (
                            <div key={job.job_id} className="flex items-center gap-4 text-sm">
                                <div className="w-4 h-4 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
                                <span className="font-bold text-slate-900">{job.filename}</span>
                                <span className="text-slate-500 flex-1">{job.message}</span>
                                <span className="font-mono font-bold text-indigo-600">{job.progress}%</span>
                            </div>
                        ))}
                    </div>
                )}

                <div className="divide-y divide-slate-100">
                    {sources.length === 0 ? (
                        <div className="p-12 text-center text-slate-400">
                            Aucun document dans la base.
                        </div>
                    ) : (
                        sources.map((source) => (
                            <div key={source.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors group">
                                <div className="flex items-center gap-4">
                                    <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center text-slate-400">
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                                    </div>
                                    <div>
                                        <p className="font-bold text-slate-900 text-sm">{source.filename}</p>
                                        <p className="text-xs text-slate-500">Ajouté le {new Date(source.upload_date).toLocaleDateString('fr-FR')}</p>
                                    </div>
                                </div>

                                <div className="flex items-center gap-4">
                                    {source.is_analyzed ? (
                                        <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
                                            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>
                                            Analysé
                                        </span>
                                    ) : (
                                        <span className="text-xs font-bold text-amber-600 bg-amber-50 px-2.5 py-1 rounded-full">En attente</span>
                                    )}

                                    <button
                                        onClick={(e) => handleDelete(source.id, e)}
                                        className="p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                                        title="Supprimer"
                                    >
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
};

export default SourceManager;
