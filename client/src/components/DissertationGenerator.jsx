import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';
import PlanRenderer from './PlanRenderer';

const DissertationGenerator = () => {
    const [subject, setSubject] = useState('');
    const [mode, setMode] = useState('plan'); // 'plan' or 'dissertation'
    const [isGenerating, setIsGenerating] = useState(false);

    // Separate states for persistence
    const [planResult, setPlanResult] = useState('');
    const [dissertationResult, setDissertationResult] = useState('');

    const [error, setError] = useState('');

    // Derived state for display
    const result = mode === 'plan' ? planResult : dissertationResult;

    // Library State
    const [showLibrary, setShowLibrary] = useState(false);
    const [folders, setFolders] = useState([]);
    const [selectedFolderId, setSelectedFolderId] = useState(null);
    const [newFolderName, setNewFolderName] = useState('');
    const [isSaving, setIsSaving] = useState(false);

    useEffect(() => {
        if (showLibrary) fetchFolders();
    }, [showLibrary]);

    const fetchFolders = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/folders`);
            if (res.ok) setFolders(await res.json());
        } catch (e) {
            console.error(e);
        }
    };

    const handleCreateFolder = async (e) => {
        e.preventDefault();
        if (!newFolderName.trim()) return;
        try {
            const res = await fetch(`${API_BASE_URL}/folders`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newFolderName })
            });
            if (res.ok) {
                setNewFolderName('');
                fetchFolders();
            }
        } catch (e) { console.error(e); }
    };

    const handleDeleteFolder = async (folderId, e) => {
        e.stopPropagation();
        if (!window.confirm("Supprimer ce dossier et tout son contenu ?")) return;
        try {
            await fetch(`${API_BASE_URL}/folders/${folderId}`, { method: 'DELETE' });
            fetchFolders();
            if (selectedFolderId === folderId) setSelectedFolderId(null);
        } catch (e) { console.error(e); }
    };

    const handleDeleteItem = async (itemId, e) => {
        e.stopPropagation();
        if (!window.confirm("Supprimer cette dissertation ?")) return;
        try {
            await fetch(`${API_BASE_URL}/library/dissertation/${itemId}`, { method: 'DELETE' });
            fetchFolders();
        } catch (e) { console.error(e); }
    };

    const handleSave = async (folderId) => {
        if (!result || !folderId) return;
        setIsSaving(true);
        try {
            const res = await fetch(`${API_BASE_URL}/library/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    folder_id: folderId,
                    subject: subject,
                    content: result,
                    type: mode
                })
            });
            if (res.ok) {
                alert("Sauvegardé avec succès !");
                fetchFolders(); // Refresh if library open
            }
        } catch (e) { console.error(e); alert("Erreur de sauvegarde"); }
        finally { setIsSaving(false); }
    };

    const loadSavedItem = (item) => {
        setSubject(item.subject);
        setMode(item.type);
        if (item.type === 'plan') {
            setPlanResult(item.content);
        } else {
            setDissertationResult(item.content);
        }
        setShowLibrary(false);
    };

    const handleGenerate = async () => {
        if (!subject.trim()) return;

        setIsGenerating(true);
        setError('');

        // Clear only the current mode's previous result if you want to start fresh 
        // or keep it? User said "tant que je n'ai pas généré de *nouvelles*".
        // Usually clicking generate implies new content, so clearing current is fine.
        if (mode === 'plan') setPlanResult('');
        else setDissertationResult('');

        const endpoint = mode === 'plan'
            ? `${API_BASE_URL}/generate_plan`
            : `${API_BASE_URL}/generate_dissertation`;

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subject: subject })
            });

            const data = await response.json();

            if (response.ok) {
                if (mode === 'plan') setPlanResult(data.plan);
                else setDissertationResult(data.dissertation);
            } else {
                setError(data.message || "Erreur lors de la génération");
            }
        } catch (err) {
            setError("Erreur de connexion au serveur");
            console.error(err);
        } finally {
            setIsGenerating(false);
        }
    };

    const handleDownload = () => {
        if (!result) return;
        const element = document.createElement("a");
        const file = new Blob([result], { type: 'text/plain' });
        element.href = URL.createObjectURL(file);
        const safeSubject = subject.substring(0, 30).replace(/[^a-z0-9]/gi, '_').toLowerCase();
        const typeLabel = mode === 'plan' ? 'plan' : 'dissertation';
        element.download = `${typeLabel}_${safeSubject}.txt`;
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    };

    return (
        <div className="flex gap-8 items-start h-[calc(100vh-140px)] animate-in fade-in duration-500">

            {/* Library Sidebar - Persistent White Card */}
            <div className={`flex-shrink-0 transition-all duration-300 ${showLibrary ? 'w-80' : 'w-0 opacity-0 overflow-hidden'}`}>
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 h-full flex flex-col overflow-hidden sticky top-0">
                    <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                        <h3 className="font-bold text-slate-900 flex items-center gap-2">
                            <svg className="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
                            Bibliothèque
                        </h3>
                        <button onClick={() => setShowLibrary(false)} className="text-slate-400 hover:text-slate-600">
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                        </button>
                    </div>

                    <div className="p-3 bg-slate-50 border-b border-slate-100">
                        <form onSubmit={handleCreateFolder} className="flex gap-2">
                            <input
                                type="text"
                                value={newFolderName}
                                onChange={(e) => setNewFolderName(e.target.value)}
                                placeholder="Nouveau dossier..."
                                className="flex-1 px-3 py-2 text-sm rounded-xl border border-slate-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                            />
                            <button type="submit" className="text-indigo-600 bg-indigo-50 hover:bg-indigo-100 p-2 rounded-xl transition-colors">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" /></svg>
                            </button>
                        </form>
                    </div>

                    <div className="flex-1 overflow-y-auto p-2 space-y-1">
                        {folders.map(folder => (
                            <div key={folder.id} className="rounded-xl overflow-hidden mb-1 border border-transparent hover:border-slate-100">
                                <div
                                    onClick={() => setSelectedFolderId(selectedFolderId === folder.id ? null : folder.id)}
                                    className={`px-3 py-2.5 flex items-center justify-between cursor-pointer transition-colors ${selectedFolderId === folder.id ? 'bg-indigo-50 text-indigo-800' : 'hover:bg-slate-50 text-slate-700'}`}
                                >
                                    <div className="flex items-center gap-2 font-bold text-sm">
                                        <svg className={`w-4 h-4 text-slate-400 transition-transform ${selectedFolderId === folder.id ? 'rotate-90 text-indigo-500' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" /></svg>
                                        {folder.name}
                                    </div>
                                    <button onClick={(e) => handleDeleteFolder(folder.id, e)} className="text-slate-300 hover:text-red-500 p-1 rounded hover:bg-red-50 transition-colors">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                    </button>
                                </div>

                                {selectedFolderId === folder.id && (
                                    <div className="bg-slate-50/50 pl-3 pr-2 py-1 space-y-1 border-t border-slate-100">
                                        {folder.dissertations.length === 0 ? (
                                            <p className="text-xs text-slate-400 italic py-2 pl-6">Aucun document</p>
                                        ) : (
                                            folder.dissertations.map(item => (
                                                <div
                                                    key={item.id}
                                                    onClick={() => loadSavedItem(item)}
                                                    className="group flex justify-between items-center cursor-pointer hover:bg-white p-2 rounded-lg transition-all border border-transparent hover:border-slate-200 hover:shadow-sm"
                                                >
                                                    <div className="min-w-0 pl-2 border-l-2 border-slate-200 group-hover:border-indigo-500">
                                                        <p className="text-xs font-bold text-slate-700 truncate group-hover:text-indigo-700">{item.subject}</p>
                                                        <p className="text-[10px] text-slate-400 uppercase tracking-wider font-bold">{item.type}</p>
                                                    </div>
                                                    <button onClick={(e) => handleDeleteItem(item.id, e)} className="text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 p-1">
                                                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                                                    </button>
                                                </div>
                                            ))
                                        )}
                                        {result && (
                                            <button
                                                onClick={() => handleSave(folder.id)}
                                                className="w-full text-center text-xs font-bold text-indigo-500 py-2 hover:bg-indigo-50 rounded-lg mt-1 border border-dashed border-indigo-200 hover:border-indigo-300 transition-colors"
                                            >
                                                + Sauvegarder ici
                                            </button>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col h-full min-w-0 gap-6">

                {/* Input Card */}
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex-shrink-0 relative">
                    <div className="flex justify-between items-start mb-6">
                        <div>
                            <div className="flex items-center gap-3">
                                <h2 className="text-2xl font-bold text-slate-900 leading-none">Atelier d'Écriture</h2>
                                {!showLibrary && (
                                    <button onClick={() => setShowLibrary(true)} className="text-xs font-bold text-indigo-600 bg-indigo-50 px-3 py-1.5 rounded-full hover:bg-indigo-100 transition-colors flex items-center gap-1">
                                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                                        Ouvrir Bibliothèque
                                    </button>
                                )}
                            </div>
                            <p className="text-slate-500 mt-2">Structurez vos idées et rédigez vos dissertations avec l'IA.</p>
                        </div>

                        <div className="bg-slate-100 p-1 rounded-xl flex items-center shadow-inner">
                            <button
                                onClick={() => setMode('plan')}
                                className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${mode === 'plan' ? 'bg-white text-slate-900 shadow-sm transform scale-105' : 'text-slate-500 hover:text-slate-700'}`}
                            >
                                📋 Plan
                            </button>
                            <button
                                onClick={() => setMode('dissertation')}
                                className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${mode === 'dissertation' ? 'bg-white text-slate-900 shadow-sm transform scale-105' : 'text-slate-500 hover:text-slate-700'}`}
                            >
                                ✍️ Dissertation
                            </button>
                        </div>
                    </div>

                    <div className="flex gap-4 items-stretch">
                        <div className="flex-1 relative">
                            <textarea
                                value={subject}
                                onChange={(e) => setSubject(e.target.value)}
                                placeholder="Entrez votre sujet ici (ex: 'L'évolution de la citoyenneté en EPS depuis 1945')..."
                                className="w-full p-4 border border-slate-200 rounded-xl focus:ring-2 focus:ring-slate-900 focus:border-transparent outline-none resize-none h-24 text-base font-medium text-slate-700 bg-slate-50 placeholder:text-slate-400"
                            />
                        </div>
                        <button
                            onClick={handleGenerate}
                            disabled={isGenerating || !subject.trim()}
                            className={`px-8 rounded-xl font-bold text-white shadow-lg transition-all flex flex-col items-center justify-center gap-2 w-48
                                ${isGenerating || !subject.trim()
                                    ? 'bg-slate-100 text-slate-300 shadow-none cursor-not-allowed'
                                    : 'bg-slate-900 hover:bg-slate-800 shadow-slate-300 hover:-translate-y-0.5 active:translate-y-0'}`}
                        >
                            {isGenerating ? (
                                <>
                                    <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                                    <span className="text-xs">Rédaction...</span>
                                </>
                            ) : (
                                <>
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                    </svg>
                                    <span>Lancer</span>
                                </>
                            )}
                        </button>
                    </div>
                </div>

                {error && (
                    <div className="bg-rose-50 text-rose-600 p-4 rounded-xl text-sm font-bold border border-rose-100 flex items-center gap-3 shadow-sm animate-in slide-in-from-top-2">
                        <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        {error}
                    </div>
                )}

                {/* Content Display - White Card */}
                <div className="flex-1 overflow-hidden bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col relative">
                    {result ? (
                        <div className="flex flex-col h-full">
                            {/* Toolbar */}
                            <div className="flex justify-between items-center p-4 border-b border-slate-100 bg-slate-50/30">
                                <div className="flex items-center gap-3">
                                    <span className={`w-2.5 h-2.5 rounded-full ${mode === 'plan' ? 'bg-emerald-500' : 'bg-indigo-500'}`}></span>
                                    <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                                        {mode === 'plan' ? 'Plan Généré' : 'Dissertation Rédigée'}
                                    </span>
                                </div>
                                <div className="flex gap-2">
                                    <button onClick={handleDownload} className="text-slate-400 hover:text-slate-900 p-2 rounded-lg hover:bg-slate-100 transition-colors" title="Télécharger .txt">
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                                    </button>
                                </div>
                            </div>

                            {/* Rich Content */}
                            <div className="flex-1 overflow-auto p-8 bg-white scroll-smooth relative">
                                <div className="max-w-4xl mx-auto">
                                    <h1 className="text-2xl font-bold text-center text-slate-900 mb-10 font-serif leading-tight">
                                        {subject}
                                    </h1>

                                    {/* Use PlanRenderer - Ensure it supports dark text for slate-900 */}
                                    <div className="text-slate-800">
                                        <PlanRenderer content={result} />
                                    </div>

                                    <div className="mt-20 pt-10 border-t border-slate-100 flex justify-center text-slate-200 gap-3">
                                        <span>•</span><span>•</span><span>•</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center text-slate-300 p-8">
                            <div className="w-20 h-20 bg-slate-50 rounded-3xl flex items-center justify-center mb-6">
                                <svg className="w-10 h-10 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                            </div>
                            <p className="text-slate-400 font-bold text-lg">Votre espace de rédaction est prêt.</p>
                            <p className="text-slate-300 text-sm mt-2">Cliquez sur "Lancer" pour démarrer.</p>
                        </div>
                    )}
                </div>

            </div>
        </div>
    );
};

export default DissertationGenerator;
