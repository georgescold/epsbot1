import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

const Revisions = () => {
    const [view, setView] = useState('dashboard'); // 'dashboard', 'review'
    const [decks, setDecks] = useState([]);
    const [activeDeck, setActiveDeck] = useState(null);
    const [reviewQueue, setReviewQueue] = useState([]);
    const [currentCardIndex, setCurrentCardIndex] = useState(0);
    const [isFlipped, setIsFlipped] = useState(false);
    const [loading, setLoading] = useState(false);
    const [generationJob, setGenerationJob] = useState(null);

    useEffect(() => {
        if (view === 'dashboard') fetchDecks();
    }, [view]);

    const [notification, setNotification] = useState(null);

    // Auto-clear notification
    useEffect(() => {
        if (notification) {
            const timer = setTimeout(() => setNotification(null), 3000);
            return () => clearTimeout(timer);
        }
    }, [notification]);

    useEffect(() => {
        let interval;
        if (generationJob && generationJob.status !== 'completed' && generationJob.status !== 'failed' && generationJob.status !== 'cancelled') {
            interval = setInterval(async () => {
                try {
                    const res = await fetch(`${API_BASE_URL}/jobs/${generationJob.id}`);
                    if (res.ok) {
                        const job = await res.json();
                        setGenerationJob(prev => ({ ...job, id: prev.id }));
                        if (job.status === 'completed') {
                            fetchDecks();
                            setTimeout(() => setGenerationJob(null), 2000);
                            setNotification({ type: 'success', text: "Génération terminée avec succès !" });
                        } else if (job.status === 'failed') {
                            setNotification({ type: 'error', text: "Erreur lors de la génération." });
                            setGenerationJob(null);
                        }
                    }
                } catch (e) { console.error(e); }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [generationJob]);

    const fetchDecks = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/revisions/decks`);
            if (res.ok) setDecks(await res.json());
        } catch (e) { console.error(e); }
    };

    const startReview = async (theme) => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/revisions/deck/${theme}/due`);
            const cards = await res.json();
            if (cards.length > 0) {
                setReviewQueue(cards);
                setActiveDeck(theme);
                setCurrentCardIndex(0);
                setIsFlipped(false);
                setView('review');
            } else {
                setNotification({ type: 'info', text: "Aucune carte à réviser pour ce thème !" });
            }
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    };

    const handleRate = async (rating) => {
        const card = reviewQueue[currentCardIndex];
        try {
            const res = await fetch(`${API_BASE_URL}/revisions/review/${card.id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rating })
            });

            if (res.ok) {
                const result = await res.json();
                console.log('Review result:', result);
            }

            // Move to next
            if (currentCardIndex < reviewQueue.length - 1) {
                setCurrentCardIndex(prev => prev + 1);
                setIsFlipped(false);
            } else {
                setNotification({ type: 'success', text: "Session terminée !" });
                setView('dashboard');
                fetchDecks();
            }
        } catch (e) { console.error(e); }
    };

    const [isConfirming, setIsConfirming] = useState(false);

    const triggerGeneration = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/revisions/generate-for-all`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                setGenerationJob({ id: data.job_id, status: 'pending', progress: 0 });
                setIsConfirming(false);
            }
        } catch (e) { console.error(e); }
    }

    // Get state label and color
    const getStateInfo = (stateName) => {
        const states = {
            'new': { label: 'Nouvelle', color: 'bg-blue-100 text-blue-700' },
            'learning': { label: 'Apprentissage', color: 'bg-amber-100 text-amber-700' },
            'review': { label: 'Révision', color: 'bg-emerald-100 text-emerald-700' },
            'relearning': { label: 'Réapprentissage', color: 'bg-orange-100 text-orange-700' }
        };
        return states[stateName] || { label: stateName, color: 'bg-slate-100 text-slate-700' };
    };

    // --- DASHBOARD VIEW ---
    if (view === 'dashboard') {
        return (
            <div className="max-w-7xl mx-auto p-6 relative">
                {/* Notification Banner */}
                {notification && (
                    <div className={`fixed top-24 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-xl shadow-lg font-bold text-sm ${notification.type === 'error' ? 'bg-red-100 text-red-700 border border-red-200' :
                        notification.type === 'success' ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' :
                            'bg-blue-100 text-blue-700 border border-blue-200'
                        }`}>
                        {notification.text}
                    </div>
                )}

                <div className="flex justify-between items-center mb-8">
                    <div>
                        <h2 className="text-3xl font-bold text-slate-900">Ancrage Mémoriel</h2>
                        <p className="text-slate-500 mt-1">Algorithme FSRS - Répétition espacée optimisée</p>
                    </div>
                    <div className="flex gap-2">
                        {isConfirming ? (
                            <>
                                <button
                                    onClick={() => setIsConfirming(false)}
                                    className="text-slate-500 px-4 py-2 font-bold text-sm hover:text-slate-700 transition-colors"
                                >
                                    Annuler
                                </button>
                                <button
                                    onClick={triggerGeneration}
                                    className="bg-red-600 text-white px-4 py-2 rounded-lg font-bold text-sm hover:bg-red-700 transition-colors shadow-sm"
                                >
                                    Confirmer ?
                                </button>
                            </>
                        ) : (
                            <button
                                onClick={() => setIsConfirming(true)}
                                disabled={!!generationJob}
                                className={`bg-slate-900 text-white px-4 py-2 rounded-lg font-bold text-sm flex items-center gap-2 shadow-sm ${generationJob ? 'opacity-80 cursor-not-allowed' : 'hover:bg-slate-800'}`}
                            >
                                {generationJob ? (
                                    <>
                                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        {generationJob.progress}%
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                                        Générer les cartes
                                    </>
                                )}
                            </button>
                        )}
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {decks.map(deck => (
                        <div key={deck.theme} className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-hidden group">
                            <div className="absolute top-0 right-0 w-32 h-32 bg-slate-50 rounded-full -translate-y-1/2 translate-x-1/2"></div>

                            <h3 className="text-xl font-bold text-slate-800 mb-4 relative z-10 capitalize">{deck.theme.replace(/_/g, ' ')}</h3>

                            <div className="flex gap-4 mb-4 relative z-10">
                                <div className="text-center">
                                    <div className="text-2xl font-bold text-emerald-500">{deck.due}</div>
                                    <div className="text-xs text-slate-400 uppercase tracking-wide">À Réviser</div>
                                </div>
                                <div className="text-center border-l border-slate-100 pl-4">
                                    <div className="text-2xl font-bold text-blue-500">{deck.new}</div>
                                    <div className="text-xs text-slate-400 uppercase tracking-wide">Nouvelles</div>
                                </div>
                                <div className="text-center border-l border-slate-100 pl-4">
                                    <div className="text-2xl font-bold text-slate-400">{deck.total}</div>
                                    <div className="text-xs text-slate-400 uppercase tracking-wide">Total</div>
                                </div>
                            </div>

                            {/* FSRS State breakdown */}
                            <div className="flex gap-2 mb-6 text-xs">
                                {deck.learning > 0 && (
                                    <span className="px-2 py-1 bg-amber-50 text-amber-600 rounded-full">
                                        {deck.learning} en cours
                                    </span>
                                )}
                                {deck.relearning > 0 && (
                                    <span className="px-2 py-1 bg-orange-50 text-orange-600 rounded-full">
                                        {deck.relearning} à revoir
                                    </span>
                                )}
                            </div>

                            <button
                                onClick={() => startReview(deck.theme)}
                                disabled={deck.due === 0}
                                className={`w-full py-3 rounded-xl font-bold relative z-10 flex justify-center items-center gap-2
                                    ${deck.due > 0
                                        ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-lg shadow-indigo-200'
                                        : 'bg-slate-100 text-slate-400 cursor-not-allowed'}`}
                            >
                                {deck.due > 0 ? 'Commencer la session' : 'À jour'}
                            </button>
                        </div>
                    ))}

                    {decks.length === 0 && (
                        <div className="col-span-full flex flex-col items-center justify-center py-20 bg-white rounded-2xl shadow-sm border border-slate-200">
                            <div className="w-16 h-1 bg-slate-50 rounded-full flex items-center justify-center mb-4 text-slate-300">
                                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
                            </div>
                            <p className="text-slate-900 font-bold text-lg mb-1">Aucune carte de révision</p>
                            <p className="text-slate-500 text-sm">Lancez une analyse de documents ou cliquez sur "Générer les cartes" pour commencer.</p>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // --- REVIEW VIEW ---
    const currentCard = reviewQueue[currentCardIndex];
    if (!currentCard) return null;

    const stateInfo = getStateInfo(currentCard.state_name);

    return (
        <div className="max-w-4xl mx-auto h-[calc(100vh-140px)] flex flex-col items-center justify-center p-6 relative">
            {/* Header / Progress */}
            <div className="absolute top-0 w-full flex justify-between items-center p-4">
                <button onClick={() => setView('dashboard')} className="text-slate-400 hover:text-slate-600 font-bold text-sm">
                    &larr; Quitter
                </button>
                <div className="flex items-center gap-4">
                    {/* Card state badge */}
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${stateInfo.color}`}>
                        {stateInfo.label}
                    </span>
                    {/* Retrievability indicator */}
                    {currentCard.retrievability !== undefined && currentCard.state !== 0 && (
                        <span className="text-xs text-slate-400">
                            Rétention: {currentCard.retrievability}%
                        </span>
                    )}
                    <div className="text-slate-400 font-mono text-sm">
                        {currentCardIndex + 1} / {reviewQueue.length}
                    </div>
                </div>
            </div>

            {/* Flashcard Area */}
            <div className="w-full max-w-2xl perspective-1000 min-h-[400px]">
                <div
                    className={`relative w-full h-full transform-style-3d cursor-pointer ${isFlipped ? 'rotate-y-180' : ''}`}
                    onClick={() => setIsFlipped(!isFlipped)}
                    style={{ minHeight: '400px' }}
                >
                    {/* Front */}
                    <div className="absolute w-full h-full backface-hidden bg-white rounded-3xl shadow-xl border border-slate-100 flex flex-col items-center justify-center p-12 text-center">
                        <div className="absolute top-6 left-1/2 -translate-x-1/2 bg-slate-100 text-slate-500 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">
                            {activeDeck.replace(/_/g, ' ')}
                        </div>
                        <h3 className="text-2xl font-bold text-slate-800 leading-snug select-none">
                            {currentCard.front}
                        </h3>
                        <div className="mt-8 text-slate-300 text-sm font-medium">
                            Cliquer pour retourner
                        </div>
                    </div>

                    {/* Back */}
                    <div className="absolute w-full h-full backface-hidden rotate-y-180 bg-white rounded-3xl shadow-xl border border-slate-100 flex flex-col items-center justify-center p-12 text-center">
                        <div className="w-16 h-1 bg-indigo-100 rounded-full mb-8"></div>
                        <p className="text-lg text-slate-700 leading-relaxed font-medium">
                            {currentCard.back}
                        </p>
                    </div>
                </div>
            </div>

            {/* Rating Controls - Only visible if flipped */}
            {isFlipped && currentCard.intervals && (
                <div className="flex gap-3 mt-8 w-full max-w-2xl">
                    <button
                        onClick={() => handleRate(1)}
                        className="flex-1 py-4 bg-rose-100 text-rose-700 font-bold rounded-xl hover:bg-rose-200 transition-colors flex flex-col items-center"
                    >
                        À revoir
                        <span className="text-xs opacity-70 font-normal mt-1">
                            {currentCard.intervals.again || '< 1m'}
                        </span>
                    </button>
                    <button
                        onClick={() => handleRate(2)}
                        className="flex-1 py-4 bg-orange-100 text-orange-700 font-bold rounded-xl hover:bg-orange-200 transition-colors flex flex-col items-center"
                    >
                        Difficile
                        <span className="text-xs opacity-70 font-normal mt-1">
                            {currentCard.intervals.hard || '1m'}
                        </span>
                    </button>
                    <button
                        onClick={() => handleRate(3)}
                        className="flex-1 py-4 bg-emerald-100 text-emerald-700 font-bold rounded-xl hover:bg-emerald-200 transition-colors flex flex-col items-center"
                    >
                        Correct
                        <span className="text-xs opacity-70 font-normal mt-1">
                            {currentCard.intervals.good || '10m'}
                        </span>
                    </button>
                    <button
                        onClick={() => handleRate(4)}
                        className="flex-1 py-4 bg-blue-100 text-blue-700 font-bold rounded-xl hover:bg-blue-200 transition-colors flex flex-col items-center"
                    >
                        Facile
                        <span className="text-xs opacity-70 font-normal mt-1">
                            {currentCard.intervals.easy || '4j'}
                        </span>
                    </button>
                </div>
            )}

            {/* Stats footer */}
            {isFlipped && (
                <div className="mt-4 flex gap-6 text-xs text-slate-400">
                    <span>Répétitions: {currentCard.reps || 0}</span>
                    <span>Oublis: {currentCard.lapses || 0}</span>
                    {currentCard.stability > 0 && (
                        <span>Stabilité: {(currentCard.stability / 100).toFixed(1)}j</span>
                    )}
                    {currentCard.difficulty > 0 && (
                        <span>Difficulté: {(currentCard.difficulty / 100).toFixed(1)}/10</span>
                    )}
                </div>
            )}
        </div>
    );
};

export default Revisions;
