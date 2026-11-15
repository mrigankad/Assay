import { useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';
import toast from 'react-hot-toast';
import api from '@/services/api';
import { useDocumentStore } from '@/stores/documentStore';
import { Icon } from '@/components/Icon';

interface Cell {
    document_id: string; question: string;
    status: 'found' | 'not_found' | 'unverified' | 'error';
    answer?: string | null; quote?: string | null; page?: number | null; source_name?: string | null;
}

const STARTERS = ['How is the price adjusted?', 'What is the contract term?', 'Is there a cap on increases?', 'What notice is needed to terminate?'];

function csvEscape(v: string) {
    return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

export function MatrixPage() {
    const { documents, fetchDocuments } = useDocumentStore();
    const [picked, setPicked] = useState<string[]>([]);
    const [questions, setQuestions] = useState<string[]>(STARTERS.slice(0, 3));
    const [draft, setDraft] = useState('');
    const [cells, setCells] = useState<Cell[] | null>(null);
    const [running, setRunning] = useState(false);
    const [open, setOpen] = useState<Cell | null>(null);

    useEffect(() => { fetchDocuments(); }, [fetchDocuments]);
    useEffect(() => {
        if (!picked.length && documents.length) setPicked(documents.filter((d) => d.status === 'completed').slice(0, 8).map((d) => d.id));
    }, [documents, picked.length]);

    const docs = useMemo(() => documents.filter((d) => picked.includes(d.id)), [documents, picked]);
    const cellAt = (doc: string, q: string) => cells?.find((c) => c.document_id === doc && c.question === q);

    async function run() {
        if (!docs.length || !questions.length) return;
        setRunning(true); setCells(null); setOpen(null);
        try {
            const r = await api.post('/matrix', { document_ids: docs.map((d) => d.id), questions }, { timeout: 600000 });
            setCells(r.data.cells);
        } catch {
            toast.error('The matrix run failed');
        } finally {
            setRunning(false);
        }
    }

    function exportCsv() {
        if (!cells) return;
        const header = ['Document', ...questions.flatMap((q) => [q, `${q} (page)`, `${q} (status)`])];
        const rows = docs.map((d) => [d.filename, ...questions.flatMap((q) => {
            const c = cellAt(d.id, q);
            return [c?.answer && c.status !== 'not_found' ? c.answer : '', c?.page ? String(c.page) : '', c?.status ?? ''];
        })]);
        const csv = [header, ...rows].map((r) => r.map(csvEscape).join(',')).join('\n');
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv' }));
        a.download = 'assay-matrix.csv';
        a.click();
        URL.revokeObjectURL(a.href);
    }

    return (
        <div className="flex h-full bg-paper">
            <div className="min-w-0 flex-1 overflow-y-auto">
                <div className="mx-auto flex max-w-[1180px] flex-col gap-[22px] px-6 py-9 lg:px-12">
                    <header className="flex flex-wrap items-end justify-between gap-4">
                        <div className="flex flex-col gap-2">
                            <span className="text-[13px] text-body">Workspace · Matrix · {docs.length} documents × {questions.length} questions</span>
                            <h1 className="font-display text-[34px] font-bold leading-none">Same questions, every document</h1>
                        </div>
                        <div className="flex gap-2">
                            <button onClick={exportCsv} disabled={!cells}
                                className="flex h-9 items-center gap-2 rounded-[10px] border border-[#D5DBD0] px-3.5 text-sm font-medium disabled:opacity-50">
                                <Icon name="table" className="h-4 w-4" />Export for Excel
                            </button>
                            <button onClick={run} disabled={running || !docs.length || !questions.length}
                                className="flex h-9 items-center gap-2 rounded-[10px] bg-ink px-3.5 text-sm font-medium text-white disabled:opacity-60">
                                <Icon name="evals" className="h-4 w-4 text-lime" />{running ? `Running ${docs.length * questions.length} cells…` : 'Run'}
                            </button>
                        </div>
                    </header>

                    <div className="flex flex-wrap items-center gap-2">
                        {questions.map((q) => (
                            <span key={q} className="flex items-center gap-1.5 rounded-full bg-bench py-1.5 pl-3 pr-2 text-[13px]">
                                {q}
                                <button onClick={() => setQuestions((qs) => qs.filter((x) => x !== q))} aria-label={`Remove ${q}`} className="text-body hover:text-dropped">
                                    <Icon name="dropped" className="h-3.5 w-3.5" />
                                </button>
                            </span>
                        ))}
                        <form onSubmit={(e) => { e.preventDefault(); const t = draft.trim(); if (t && !questions.includes(t)) setQuestions([...questions, t]); setDraft(''); }}
                            className="flex items-center gap-1.5 rounded-full border border-dashed border-[#C9D0C4] py-1 pl-3 pr-1">
                            <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Add a question"
                                className="w-44 bg-transparent text-[13px] outline-none placeholder:text-muted" />
                            <button type="submit" className="rounded-full bg-ink p-1 text-lime" aria-label="Add question"><Icon name="plus" className="h-3.5 w-3.5" strokeWidth={2} /></button>
                        </form>
                    </div>

                    {!documents.length ? (
                        <p className="rounded-xl bg-bench px-4 py-3 text-sm text-body">Upload documents first, then compare them here.</p>
                    ) : (
                        <div className="overflow-x-auto">
                            <div className="flex min-w-[720px] flex-col border-t border-ink text-sm">
                                <div className="flex border-b border-rule text-xs font-semibold text-body">
                                    <span className="w-[220px] shrink-0 py-3">Document</span>
                                    {questions.map((q) => <span key={q} className="flex-1 border-l border-[#EEF1EA] px-3.5 py-3">{q}</span>)}
                                </div>
                                {documents.filter((d) => d.status === 'completed').map((d) => {
                                    const on = picked.includes(d.id);
                                    return (
                                        <div key={d.id} className={clsx('flex border-b border-[#EEF1EA]', !on && 'opacity-45')}>
                                            <button onClick={() => setPicked((p) => on ? p.filter((x) => x !== d.id) : [...p, d.id])}
                                                className="flex w-[220px] shrink-0 items-center gap-2 py-3 pr-2 text-left font-semibold">
                                                <span className={clsx('flex h-4 w-4 shrink-0 items-center justify-center rounded', on ? 'bg-ink' : 'border border-[#C9D0C4]')}>
                                                    {on && <Icon name="check" className="h-3 w-3 text-lime" strokeWidth={3} />}
                                                </span>
                                                <span className="truncate">{d.filename}</span>
                                            </button>
                                            {questions.map((q) => {
                                                const c = on ? cellAt(d.id, q) : undefined;
                                                const tone = !c ? '' : c.status === 'found' ? '' : c.status === 'unverified' ? 'bg-[#FBF4E4]' : c.status === 'not_found' ? 'bg-[#FCEFEA]' : 'bg-bench';
                                                return (
                                                    <button key={q} disabled={!c} onClick={() => c && setOpen(c)}
                                                        className={clsx('flex flex-1 flex-col gap-[3px] border-l border-[#EEF1EA] px-3.5 py-3 text-left', tone, open === c && c && 'ring-2 ring-inset ring-ink')}>
                                                        {!on ? <span className="text-muted">-</span> : running ? <span className="h-3 w-24 animate-pulse rounded bg-rule" /> : !c ? <span className="text-muted">Not run</span> : (
                                                            <>
                                                                <span className={clsx('font-medium', c.status === 'not_found' && 'text-dropped', c.status === 'error' && 'text-body')}>
                                                                    {c.status === 'not_found' ? 'Not found' : c.status === 'error' ? 'Failed' : c.answer}
                                                                </span>
                                                                <span className={clsx('text-[11px] font-semibold',
                                                                    c.status === 'found' ? 'text-assay' : c.status === 'unverified' ? 'text-conflict' : 'text-dropped')}>
                                                                    {c.status === 'found' ? `p. ${c.page ?? '?'}` : c.status === 'unverified' ? 'quote not in source' : c.status === 'not_found' ? 'searched this document' : ''}
                                                                </span>
                                                            </>
                                                        )}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    <div className="flex flex-wrap items-center gap-5 text-[13px] text-body">
                        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px] bg-assay" />Answer with the quote found in the page</span>
                        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px] bg-conflict" />Model's quote not found in the source</span>
                        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px] bg-dropped" />Not in this document</span>
                    </div>
                </div>
            </div>

            {open && (
                <aside className="hidden w-[380px] shrink-0 flex-col gap-3 border-l border-rule bg-[#EEF1EA] p-5 xl:flex">
                    <div className="flex items-start justify-between gap-3">
                        <span className="text-sm font-semibold">{open.question}</span>
                        <button onClick={() => setOpen(null)} aria-label="Close" className="text-body"><Icon name="dropped" className="h-5 w-5" /></button>
                    </div>
                    <span className="text-xs text-body">{open.source_name}{open.page ? ` · page ${open.page}` : ''}</span>
                    <p className="font-display text-xl font-bold">{open.status === 'not_found' ? 'Not found' : open.answer}</p>
                    {open.quote && (
                        <div className={clsx('rounded border-2 px-3 py-2 font-prose text-[15px] leading-6',
                            open.status === 'found' ? 'border-assay bg-lime-wash' : 'border-conflict bg-[#FBF4E4]')}>
                            “{open.quote}”
                        </div>
                    )}
                    {open.status === 'unverified' && <p className="text-[13px] text-conflict">The model quoted text that isn't in the retrieved passages, so this cell is not trusted.</p>}
                </aside>
            )}
        </div>
    );
}
