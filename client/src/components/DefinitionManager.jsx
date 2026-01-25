
import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';


const DefinitionManager = () => {
    const [sources, setSources] = useState([]);
    const [uploading, setUploading] = useState(false);

    useEffect(() => {
        fetchSources();
    }, []);

    const fetchSources = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/definitions`);
            const data = await res.json();
            setSources(data);
        } catch (error) {
            console.error("Error fetching definitions:", error);
        }
    };

    const handleUpload = async (event) => {
        if (!event.target.files.length) return;
        setUploading(true);

        const formData = new FormData();
        for (const file of event.target.files) {
            formData.append('file', file);
            // We process one by one purely for simple UI feedback in this quick implementation
            // Ideally batch or parallel, but one endpoint call per file is defined currently in main.py logic (single file param)
            // Actually main.py expects 'file' not list.
            // So loop here.
        }

        // Since main.py endpoint is single file, loop here
        for (const file of event.target.files) {
            const fd = new FormData();
            fd.append('file', file);
            try {
                await fetch(`${API_BASE_URL}/definitions/upload`, {
                    method: 'POST',
                    body: fd
                });
            } catch (e) {
                console.error(e);
            }
        }

        setUploading(false);
        fetchSources();
    };

    const handleDelete = async (id) => {
        // if (!window.confirm("Supprimer ce fichier ?")) return;
        try {
            await fetch(`${API_BASE_URL}/definitions/${id}`, { method: 'DELETE' });
            fetchSources();
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-8">
            {/* Header Section */}
            <div className="text-center space-y-2">
                <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Définitions & Citations</h2>
                <p className="text-slate-500 font-medium">Documents d'appui pour l'introduction et la conclusion</p>
            </div>

            {/* Upload Box */}
            <div className={`relative bg-white rounded-xl border-2 border-dashed transition-all p-12 text-center group ${uploading ? 'border-amber-400 bg-amber-50' : 'border-gray-200 hover:border-amber-400'}`}>
                <input type="file" accept="application/pdf" multiple onChange={handleUpload} className="hidden" id="def-upload" disabled={uploading} />

                <label htmlFor="def-upload" className="cursor-pointer block">
                    {uploading ? (
                        <div className="max-w-md mx-auto">
                            <div className="text-sm font-semibold text-amber-600 mb-2 animate-pulse">ANALYSE EN COURS...</div>
                            <p className="text-gray-500 text-sm">Extraction des définitions et citations...</p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div className="w-16 h-16 bg-amber-50 rounded-full flex items-center justify-center mx-auto group-hover:bg-amber-400 transition-colors duration-300">
                                <svg className="w-8 h-8 text-amber-300 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-slate-900">Ajouter des sources de définitions</h3>
                                <p className="text-sm text-gray-500 mt-1">PDF uniquement (Dictionnaires, Lexiques, Citations)</p>
                            </div>
                        </div>
                    )}
                </label>
            </div>

            {/* List */}
            <div className="bg-white rounded-xl shadow-sm overflow-hidden border border-gray-100">
                <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
                    <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Fichiers disponibles ({sources.length})</h3>
                </div>
                {sources.length === 0 ? (
                    <div className="p-8 text-center text-gray-400 italic">Aucun document ajouté</div>
                ) : (
                    <div className="divide-y divide-gray-100">
                        {sources.map(src => (
                            <div key={src.id} className="px-6 py-4 flex items-center justify-between hover:bg-gray-50">
                                <div className="flex items-center gap-4">
                                    <div className="w-10 h-10 rounded bg-amber-50 flex items-center justify-center text-amber-500 font-bold text-xs">DEF</div>
                                    <div>
                                        <p className="text-sm font-semibold text-slate-800">{src.filename}</p>
                                        <p className="text-xs text-gray-400 mt-0.5">Ajouté le {new Date(src.upload_date).toLocaleDateString()}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-4">
                                    {src.is_analyzed && <span className="text-xs font-bold text-emerald-500 bg-emerald-50 px-2 py-1 rounded">PRÊT</span>}
                                    <button onClick={() => handleDelete(src.id)} className="text-gray-400 hover:text-red-500 transition-colors">
                                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default DefinitionManager;
