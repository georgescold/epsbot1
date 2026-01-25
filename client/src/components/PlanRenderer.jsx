import React from 'react';

// Copied and adapted from SheetViewer/FormatText logic for consistency
const FormatRichText = ({ text }) => {
    if (!text) return null;

    // Helper to process inline formatting (bold, italic)
    const renderInline = (content, keyPrefix) => {
        // Regex for **bold** and *italic*
        // Split keeps delimiters, so we need to process carefully
        // Simple parser: split by ** then *

        const parts = content.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);

        return parts.map((part, idx) => {
            const key = `${keyPrefix}-${idx}`;

            if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={key} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
            }
            if (part.startsWith('*') && part.endsWith('*')) {
                return <em key={key} className="italic text-slate-800 bg-slate-100 px-1 rounded">{part.slice(1, -1)}</em>;
            }
            return <span key={key}>{part}</span>;
        });
    };

    // First split by Author pattern
    const parts = text.split(/(\([^)]+\))/g);

    return (
        <span>
            {parts.map((part, i) => {
                if (part.startsWith('(') && part.endsWith(')')) {
                    const content = part.slice(1, -1);

                    // Case: (Author, in Title, Year) etc.
                    // Reuse existing logic but simplified for brevity in this replace
                    if (content.includes(' in ')) {
                        const [authorSection, ...rest] = content.split(' in ');
                        const remainder = rest.join(' in ');
                        let titleSection = remainder;
                        let year = '';
                        if (remainder.match(/,\s*\d{4}$/)) {
                            const lastCommaIndex = remainder.lastIndexOf(',');
                            titleSection = remainder.substring(0, lastCommaIndex);
                            year = remainder.substring(lastCommaIndex);
                        }
                        return (
                            <span key={i}>
                                (<span className="bg-[#bbf7d0] text-slate-900 px-1 rounded mx-0.5 font-semibold box-decoration-clone">{authorSection.trim()}</span>
                                , in <span className="italic text-slate-700">{titleSection.trim()}</span>
                                {year})
                            </span>
                        );
                    }

                    if (/\d/.test(content) || content.includes(',')) {
                        const subParts = content.split(',');
                        const author = subParts[0];
                        const remainder = subParts.slice(1).join(',');
                        return (
                            <span key={i}>
                                (<span className="bg-[#bbf7d0] text-slate-900 px-1 rounded mx-0.5 font-semibold box-decoration-clone">{author.trim()}</span>
                                {remainder ? `,${remainder}` : ''})
                            </span>
                        );
                    }
                }
                // Render regular text with markdown support
                return <span key={i}>{renderInline(part, `text-${i}`)}</span>;
            })}
        </span>
    );
};

const PlanRenderer = ({ content }) => {
    if (!content) return null;

    // Split content by lines to identify headers vs body text
    const lines = content.split('\n');

    return (
        <div className="font-serif text-slate-800 leading-relaxed text-lg space-y-4">
            {lines.map((line, idx) => {
                const trimmed = line.trim();
                if (!trimmed) return <br key={idx} />;

                // Identify Headers
                const isMainTitle = trimmed.match(/^(Introduction|Conclusion|I\.|II\.|III\.)/i) || trimmed.startsWith('###');
                const isSubTitle = trimmed.match(/^[A-Z]\)/) || trimmed.match(/^\d+\./) || trimmed.startsWith('####');

                if (isMainTitle) {
                    // Cleaner title, remove markdown chars if any
                    const cleanTitle = trimmed.replace(/^#+\s*/, '').replace(/\*+/g, '').trim();
                    return (
                        <h3 key={idx} className="text-2xl font-bold text-indigo-700 mt-8 mb-4 border-b border-indigo-100 pb-2">
                            {cleanTitle}
                        </h3>
                    );
                }

                if (isSubTitle) {
                    const cleanSub = trimmed.replace(/^####\s*/, '');
                    return (
                        <h4 key={idx} className="text-xl font-semibold text-slate-900 mt-6 mb-2 pl-4 border-l-4 border-emerald-400">
                            {cleanSub}
                        </h4>
                    );
                }

                // Bullet points
                if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                    return (
                        <div key={idx} className="flex gap-3 ml-4">
                            <span className="text-indigo-400 mt-1.5">•</span>
                            <p className="flex-1">
                                <FormatRichText text={trimmed.substring(2)} />
                            </p>
                        </div>
                    );
                }

                // Regular Paragraph
                return (
                    <p key={idx} className="text-justify mb-2">
                        <FormatRichText text={trimmed} />
                    </p>
                );
            })}
        </div>
    );
};

export default PlanRenderer;
