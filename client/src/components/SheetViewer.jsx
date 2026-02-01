import React, { useState } from 'react';
import { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, BorderStyle, WidthType, AlignmentType, HeadingLevel, ShadingType } from 'docx';
import { saveAs } from 'file-saver';
import { API_BASE_URL } from '../config';

const SHEETS = [
    { id: "citoyennete", title: "Citoyenneté" },
    { id: "conceptions", title: "Conceptions" },
    { id: "contexte", title: "Contexte Sociétal" },
    { id: "evaluation", title: "Évaluation" },
    { id: "formation_enseignants", title: "Formation Enseignants" },
    { id: "orthodoxie_scolaire", title: "Orthodoxie Scolaire" },
    { id: "pratiques_enseignantes", title: "Pratiques Enseignantes" },
    { id: "representations_corps", title: "Représentations Corps" },
    { id: "sciences", title: "Sciences et EPS" },
    { id: "sport_scolaire", title: "Sport Scolaire" },
    { id: "systeme_scolaire", title: "Système Scolaire" },
    { id: "textes_institutionnels", title: "Textes Institutionnels" },
    { id: "effort", title: "Effort" },
];

const FormatText = ({ text }) => {
    if (!text) return null;
    const parts = text.split(/(\([^)]+\))/g);

    return (
        <span>
            {parts.map((part, i) => {
                if (part.startsWith('(') && part.endsWith(')')) {
                    const content = part.slice(1, -1);
                    if (content.includes(' in ')) {
                        const [authorSection, ...rest] = content.split(' in ');
                        const [titleSection, ...end] = rest.join(' in ').split(',');
                        const year = end.join(',');

                        return (
                            <span key={i}>
                                (<span className="bg-[#bbf7d0] text-slate-900 px-0.5 rounded box-decoration-clone">{authorSection.trim()}</span>
                                , in <span className="underline decoration-slate-400 underline-offset-4">{titleSection.trim()}</span>
                                {year ? `,${year}` : ''})
                            </span>
                        );
                    }
                    if (content.includes(',') && /\d/.test(content)) {
                        const subParts = content.split(',');
                        const author = subParts[0];
                        const remainder = subParts.slice(1).join(',');
                        if (!/^\d+$/.test(author.trim())) {
                            return (
                                <span key={i}>
                                    (<span className="bg-[#bbf7d0] text-slate-900 px-0.5 rounded box-decoration-clone">{author.trim()}</span>,
                                    {remainder})
                                </span>
                            );
                        }
                    }
                }
                return part;
            })}
        </span>
    );
};

const SheetViewer = () => {
    const [activeSheet, setActiveSheet] = useState(SHEETS[0].id);
    const [sheetData, setSheetData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [isUpdating, setIsUpdating] = useState(false); // State for smart update spinner
    const [updateStatus, setUpdateStatus] = useState(null); // 'success' | 'error' | null

    const fetchSheet = async (sheetId) => {
        setLoading(true);
        setActiveSheet(sheetId);
        try {
            const res = await fetch(`${API_BASE_URL}/sheets/${sheetId}`);
            setSheetData(await res.json());
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    const handleSmartUpdate = async () => {
        setIsUpdating(true);
        setUpdateStatus(null);
        try {
            // "Optimiser toutes les fiches" : Fetch ALL sheets in parallel
            const promises = SHEETS.map(sheet => fetch(`${API_BASE_URL}/sheets/${sheet.id}`).then(r => r.json()));
            const results = await Promise.all(promises);

            // Find the result for the currently active sheet to refresh the view
            const activeIndex = SHEETS.findIndex(s => s.id === activeSheet);
            const newData = activeIndex !== -1 ? results[activeIndex] : null;

            setTimeout(() => {
                if (newData) setSheetData(newData);
                setIsUpdating(false);
                setUpdateStatus('success');
                setTimeout(() => setUpdateStatus(null), 3000);
            }, 800);
        } catch (err) {
            console.error("Global update failed", err);
            setIsUpdating(false);
            setUpdateStatus('error');
            setTimeout(() => setUpdateStatus(null), 3000);
        }
    };

    // Helper function to check if year is already in content text
    const contentContainsYear = (content, year) => {
        if (!year || !content) return false;
        // Extract 4-digit year from the year field
        const yearMatch = String(year).match(/\d{4}/);
        if (!yearMatch) return false;
        return content.includes(yearMatch[0]);
    };

    // Helper to build text runs with highlighted year
    const buildProofTextRuns = (content, year, isNuance) => {
        // All text in black for both nuance and proof
        const textColor = "1E293B";

        // Safety check - if content is empty, return empty array
        if (!content || !content.trim()) {
            return [new TextRun({ text: "[Contenu manquant]", size: 20, color: "94A3B8", font: "Sora" })];
        }

        // If no year or year already in content, just return plain text
        if (!year || contentContainsYear(content, year)) {
            // Try to highlight the year in the content if it exists
            const yearMatch = content.match(/\(?\d{4}\)?/);
            if (yearMatch) {
                const parts = content.split(yearMatch[0]);
                const runs = [];

                // Add text before year (if exists)
                if (parts[0]) {
                    runs.push(new TextRun({ text: parts[0], size: 20, color: textColor, font: "Sora" }));
                }

                // Add highlighted year
                runs.push(new TextRun({
                    text: yearMatch[0],
                    size: 20,
                    color: textColor,
                    bold: true,
                    shading: { type: ShadingType.SOLID, color: "FEF08A", fill: "FEF08A" }, // Yellow highlight
                    font: "Sora"
                }));

                // Add text after year (if exists)
                const afterText = parts.slice(1).join(yearMatch[0]);
                if (afterText) {
                    runs.push(new TextRun({ text: afterText, size: 20, color: textColor, font: "Sora" }));
                }

                return runs;
            }
            return [new TextRun({ text: content, size: 20, color: textColor, font: "Sora" })];
        }

        // Year not in content, append it with highlight
        return [
            new TextRun({ text: content + " ", size: 20, color: textColor, font: "Sora" }),
            new TextRun({
                text: `(${year})`,
                size: 20,
                color: textColor,
                bold: true,
                shading: { type: ShadingType.SOLID, color: "FEF08A", fill: "FEF08A" }, // Yellow highlight
                font: "Sora"
            })
        ];
    };

    const downloadWord = async () => {
        if (!sheetData) return;

        const sheetTitle = SHEETS.find(s => s.id === activeSheet)?.title || '';
        const children = [];

        // === TITLE ===
        children.push(
            new Paragraph({
                children: [
                    new TextRun({
                        text: sheetTitle,
                        bold: true,
                        size: 56, // 28pt
                        color: "0F172A",
                        font: "Sora",
                    }),
                ],
                heading: HeadingLevel.TITLE,
                spacing: { after: 600 },
            })
        );

        // === CONTENT BY PERIOD ===
        Object.keys(sheetData).forEach((period) => {
            const args = sheetData[period];
            if (args.length === 0) return;

            // Period Header - Clean and readable style
            children.push(
                new Paragraph({
                    children: [
                        new TextRun({
                            text: period,
                            bold: true,
                            size: 28, // 14pt
                            color: "4F46E5", // Indigo color
                            font: "Sora",
                        }),
                    ],
                    border: {
                        bottom: {
                            color: "4F46E5",
                            size: 12,
                            style: BorderStyle.SINGLE,
                            space: 4,
                        },
                    },
                    spacing: { before: 600, after: 400 },
                })
            );

            // Arguments
            args.forEach((arg, argIndex) => {
                // Argument content (bold) with more spacing
                children.push(
                    new Paragraph({
                        children: [
                            new TextRun({
                                text: arg.content,
                                bold: true,
                                size: 24, // 12pt
                                color: "0F172A",
                                font: "Sora",
                            }),
                        ],
                        spacing: { before: 400, after: 300 },
                        border: {
                            left: {
                                color: "4F46E5",
                                size: 24,
                                style: BorderStyle.SINGLE,
                                space: 10,
                            },
                        },
                        indent: { left: 200 },
                    })
                );

                // Proofs with improved colors and spacing - skip empty proofs
                arg.proofs.forEach((proof) => {
                    // Skip proofs with no content
                    if (!proof.content || !proof.content.trim()) return;

                    const isNuance = proof.is_nuance;
                    // Nuance: red label + red border, light red bg; Proof: green bg
                    const labelColor = isNuance ? "DC2626" : "166534"; // Red for nuance, dark green for proof
                    const labelText = isNuance ? "Nuance : " : "Preuve : ";
                    const bgColor = isNuance ? "FEF2F2" : "DCFCE7"; // Light red for nuance, light green for proof
                    const borderColor = isNuance ? "DC2626" : "22C55E"; // Red for nuance, green for proof

                    const proofTextRuns = buildProofTextRuns(proof.content, proof.year, isNuance);

                    children.push(
                        new Paragraph({
                            children: [
                                new TextRun({
                                    text: labelText,
                                    bold: true,
                                    size: 20, // 10pt
                                    color: labelColor,
                                    font: "Sora",
                                }),
                                ...proofTextRuns
                            ],
                            shading: {
                                type: ShadingType.SOLID,
                                color: bgColor,
                                fill: bgColor,
                            },
                            border: {
                                left: {
                                    color: borderColor,
                                    size: 18,
                                    style: BorderStyle.SINGLE,
                                    space: 8,
                                },
                            },
                            spacing: { before: 200, after: 200 },
                            indent: { left: 400 },
                        })
                    );

                    // Citation/complement - NOT italic, black text
                    if (proof.complement && proof.complement.trim() && !proof.complement.toLowerCase().includes('non disponible')) {
                        children.push(
                            new Paragraph({
                                children: [
                                    new TextRun({
                                        text: `"${proof.complement}"`,
                                        size: 18, // 9pt
                                        color: "1E293B", // Black
                                        font: "Sora",
                                    }),
                                ],
                                spacing: { before: 100, after: 250 },
                                indent: { left: 600 },
                            })
                        );
                    }
                });

                // Source with more spacing after
                children.push(
                    new Paragraph({
                        children: [
                            new TextRun({
                                text: `Source : ${arg.source}`,
                                size: 16, // 8pt
                                color: "94A3B8",
                                font: "Sora",
                            }),
                        ],
                        alignment: AlignmentType.RIGHT,
                        spacing: { before: 150, after: 450 },
                    })
                );

                // Add extra spacing between arguments
                if (argIndex < args.length - 1) {
                    children.push(
                        new Paragraph({
                            children: [],
                            spacing: { before: 100, after: 100 },
                        })
                    );
                }
            });
        });

        // Create document with Sora font as default
        const doc = new Document({
            styles: {
                default: {
                    document: {
                        run: {
                            font: "Sora",
                        },
                    },
                },
            },
            sections: [{
                properties: {
                    page: {
                        margin: {
                            top: 1000,
                            right: 1000,
                            bottom: 1000,
                            left: 1000,
                        },
                    },
                },
                children: children,
            }],
        });

        // Generate and download
        const blob = await Packer.toBlob(doc);
        saveAs(blob, `fiche_${activeSheet}.docx`);
    };

    return (
        <div className="flex flex-col lg:flex-row gap-8 items-start animate-in fade-in duration-500">
            {/* Sidebar Navigation - White Card */}
            <div className="w-full lg:w-72 flex-shrink-0 sticky top-24 z-10">
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                    <div className="p-4 border-b border-slate-100 bg-slate-50/50">
                        <h3 className="font-bold text-slate-900 flex items-center gap-2">
                            <svg className="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                            Thématiques
                        </h3>
                    </div>
                    <div className="max-h-[calc(100vh-200px)] overflow-y-auto p-2 space-y-1">
                        {SHEETS.map((sheet) => (
                            <button
                                key={sheet.id}
                                onClick={() => fetchSheet(sheet.id)}
                                className={`w-full text-left px-4 py-3 rounded-xl text-sm transition-all flex items-center justify-between group ${activeSheet === sheet.id
                                    ? 'bg-slate-900 text-white font-bold shadow-md'
                                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900 font-medium'
                                    }`}
                            >
                                {sheet.title}
                                {activeSheet === sheet.id && <div className="w-2 h-2 bg-white rounded-full"></div>}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Main Content Area - White Card (Container) - Actually transparent container for cards inside */}
            <div className="flex-1 min-w-0 flex flex-col gap-6">

                {/* Header Bar */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col md:flex-row justify-between items-center gap-4">
                    <div>
                        <h2 className="text-2xl font-extrabold text-slate-900 leading-tight">
                            {SHEETS.find(s => s.id === activeSheet)?.title}
                        </h2>
                        <p className="text-slate-500 font-medium text-sm">Synthèse et Arguments Chronologiques</p>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={handleSmartUpdate}
                            disabled={!sheetData || loading || isUpdating}
                            className={`
                                    px-4 py-2.5 rounded-xl font-bold text-xs uppercase tracking-wide flex items-center gap-2 border transition-all
                                    ${isUpdating
                                    ? 'bg-emerald-50 text-emerald-600 border-emerald-200'
                                    : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                                }
                                `}
                        >
                            <svg className={`w-4 h-4 ${isUpdating ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                            </svg>
                            {isUpdating ? 'Optimisation...' : 'MAJ'}
                        </button>

                        <button
                            onClick={downloadWord}
                            disabled={!sheetData || loading}
                            className="bg-slate-900 hover:bg-slate-800 text-white font-bold py-2.5 px-6 rounded-xl shadow-lg transition-all flex items-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                            Word
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div>
                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-32 bg-white rounded-2xl shadow-sm border border-slate-200">
                            <div className="w-12 h-12 border-4 border-slate-200 border-t-slate-900 rounded-full animate-spin mb-4"></div>
                            <p className="text-slate-900 font-bold">Chargement de l'analyse...</p>
                        </div>
                    ) : sheetData ? (
                        <div className="space-y-8">
                            {Object.keys(sheetData).map((period) => (
                                sheetData[period].length > 0 && (
                                    <div key={period} className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
                                        <div className="mb-6 flex items-center gap-4">
                                            <div className="h-8 w-1 bg-slate-900 rounded-full"></div>
                                            <h3 className="text-xl font-bold text-slate-900 tracking-tight">{period}</h3>
                                        </div>

                                        <div className="space-y-8">
                                            {sheetData[period].map((arg, idx) => (
                                                <div key={idx} className="group">
                                                    <div className="pl-4 border-l-2 border-slate-200 group-hover:border-slate-900 transition-colors">
                                                        <p className="font-bold text-slate-800 mb-4 text-lg leading-relaxed">
                                                            <FormatText text={arg.content} />
                                                        </p>

                                                        <div className="space-y-4">
                                                            {arg.proofs.map((proof, pIdx) => (
                                                                <div key={pIdx} className={`rounded-xl p-4 border transition-all ${proof.is_nuance
                                                                    ? 'bg-rose-50/50 border-rose-100 text-rose-900'
                                                                    : 'bg-slate-50 border-slate-100 text-slate-700'
                                                                    }`}>
                                                                    <div className="flex gap-2 items-start">
                                                                        <span className={`shrink-0 mt-0.5 w-2 h-2 rounded-full ${proof.is_nuance ? 'bg-rose-500' : 'bg-indigo-500'}`}></span>
                                                                        <div className="text-sm leading-relaxed">
                                                                            <span className={`font-bold mr-1 ${proof.is_nuance ? 'text-rose-700' : 'text-slate-900'}`}>
                                                                                {proof.is_nuance ? 'Nuance :' : 'Preuve :'}
                                                                            </span>
                                                                            <FormatText text={proof.content} />
                                                                            {proof.year && <span className="font-mono text-xs font-extrabold ml-2 bg-slate-900 text-white px-2 py-1 rounded shadow-sm">{proof.year}</span>}
                                                                        </div>
                                                                    </div>

                                                                    {proof.complement && proof.complement.trim() && !proof.complement.toLowerCase().includes('non disponible') && (
                                                                        <div className="mt-2 ml-4 pl-3 border-l-2 border-slate-200/50 text-xs italic opacity-80">
                                                                            "<FormatText text={proof.complement} />"
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            ))}
                                                        </div>
                                                        <div className="mt-3 flex justify-end">
                                                            <span className="text-[10px] uppercase font-bold text-slate-300 tracking-widest">{arg.source}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )
                            ))}
                            {Object.values(sheetData).every(arr => arr.length === 0) && (
                                <div className="text-center py-20 bg-white rounded-2xl border border-slate-200">
                                    <p className="text-slate-400 font-medium">Aucune donnée pour cette thématique.</p>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="text-center py-32 bg-white rounded-2xl border border-dashed border-slate-300">
                            <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
                            </div>
                            <p className="text-slate-400 font-medium text-lg">Sélectionnez une thématique à gauche pour visualiser les fiches.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default SheetViewer;
