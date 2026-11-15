import { Children, Fragment, isValidElement, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import clsx from 'clsx';
import { useChatStore } from '@/stores/chatStore';
import api from '@/services/api';
import { Icon } from '@/components/Icon';
import type { Evidence, Message, ProgressStage } from '@/types';

const STAGES: { key: ProgressStage[]; label: string; icon: string }[] = [
    { key: ['understanding', 'routing', 'planning'], label: 'Plan', icon: 'planner' },
    { key: ['retrieving', 'reranking', 'found_sources'], label: 'Search', icon: 'search' },
    { key: ['synthesizing'], label: 'Write', icon: 'ask' },
    { key: ['verifying', 'finalizing'], label: 'Verify', icon: 'verify' },
];

const SUGGESTIONS = [
    'What changed in the price adjustment terms, and where does it say so?',
    'Summarise the main risks, with the page for each one.',
    'Do any two documents disagree on the same figure?',
];

function stageIndex(m: Message) {
    if (m.status === 'done') return STAGES.length;
    const s = m.stage?.stage;
    const i = STAGES.findIndex((g) => s && g.key.includes(s));
    return i < 0 ? 0 : i;
}

/** Turn "[3]" markers inside answer text into clickable citation chips. */
function withCitations(children: ReactNode, onCite: (n: number) => void, valid: Set<number>): ReactNode {
    return Children.map(children, (child) => {
        if (typeof child === 'string') {
            const parts = child.split(/(\[\d+\])/g);
            return parts.map((part, i) => {
                const m = part.match(/^\[(\d+)\]$/);
                if (!m) return <Fragment key={i}>{part}</Fragment>;
                const n = Number(m[1]);
                return (
                    <button key={i} onClick={() => onCite(n)}
                        className={clsx('mx-0.5 align-baseline font-sans text-[12px] font-bold', valid.has(n) ? 'text-assay hover:underline' : 'text-dropped line-through')}
                        title={valid.has(n) ? `Open source ${n}` : 'Citation without a source'}>
                        [{n}]
                    </button>
                );
            });
        }
        if (isValidElement<{ children?: ReactNode }>(child) && child.props.children) {
            return child;
        }
        return child;
    });
}

function StagePills({ m }: { m: Message }) {
    const at = stageIndex(m);
    return (
        <div className="flex flex-wrap items-center gap-1.5 text-[13px]">
            {STAGES.map((s, i) => {
                const done = i < at;
                const live = i === at && m.status !== 'done' && m.status !== 'error';
                return (
                    <span key={s.label} className={clsx('flex h-[30px] items-center gap-1.5 rounded-full px-2.5',
                        i === STAGES.length - 1 && done ? 'bg-lime font-semibold' : done ? 'bg-bench' : live ? 'bg-ink text-white' : 'bg-bench text-muted')}>
                        <Icon name={s.icon} className={clsx('h-[15px] w-[15px]', live && 'text-lime')} />
                        {s.label}{live && '…'}
                    </span>
                );
            })}
            {m.latency_ms ? <span className="ml-1 text-body">{(m.latency_ms / 1000).toFixed(1)} s</span> : null}
        </div>
    );
}

function Answer({ m, onCite }: { m: Message; onCite: (n: number) => void }) {
    const valid = useMemo(() => new Set((m.evidence ?? []).map((_, i) => i + 1)), [m.evidence]);
    const cite = (c: ReactNode) => withCitations(c, onCite, valid);
    if (m.status === 'error') {
        return <p className="rounded-xl bg-dropped/5 px-4 py-3 text-sm text-dropped">{m.error || 'Something went wrong.'}</p>;
    }
    if (!m.content) return <p className="font-prose text-[19px] text-muted">Reading the evidence…</p>;
    return (
        <div className="font-prose text-[19px] leading-[30px] text-[#1E2620]">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
                p: ({ children }) => <p className="mb-4">{cite(children)}</p>,
                li: ({ children }) => <li className="mb-1.5 ml-5 list-disc">{cite(children)}</li>,
                strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                h1: ({ children }) => <h3 className="mb-2 mt-4 font-display text-xl font-bold">{children}</h3>,
                h2: ({ children }) => <h3 className="mb-2 mt-4 font-display text-xl font-bold">{children}</h3>,
                h3: ({ children }) => <h3 className="mb-2 mt-4 font-display text-lg font-bold">{children}</h3>,
                table: ({ children }) => <div className="my-3 overflow-x-auto font-sans text-sm"><table className="w-full">{children}</table></div>,
                th: ({ children }) => <th className="border-b border-ink py-1.5 pr-4 text-left text-xs font-semibold text-body">{children}</th>,
                td: ({ children }) => <td className="border-b border-rule py-1.5 pr-4">{cite(children)}</td>,
            }}>{m.content}</ReactMarkdown>
        </div>
    );
}

function Sources({ ev, selected, onSelect }: { ev: Evidence[]; selected: number | null; onSelect: (n: number) => void }) {
    if (!ev.length) return null;
    return (
        <div className="flex flex-col border-t border-rule pt-3 text-[13px]">
            {ev.map((e, i) => (
                <button key={e.id} onClick={() => onSelect(i + 1)}
                    className={clsx('flex items-center gap-3 border-b border-[#EEF1EA] py-2 text-left', selected === i + 1 && 'bg-[#F7FCE8]')}>
                    <span className="w-7 shrink-0 font-bold text-assay">[{i + 1}]</span>
                    <span className="flex min-w-0 flex-1 items-center gap-2">
                        <Icon name={e.type === 'web' ? 'web' : e.type === 'sql' ? 'table' : 'document'} className="h-4 w-4 shrink-0 text-body" />
                        <span className={clsx('truncate', selected === i + 1 && 'font-semibold')}>{e.title || e.source_name}</span>
                    </span>
                    <span className="w-16 shrink-0 text-body">{e.locator.page ? `p. ${e.locator.page}` : e.type}</span>
                    <span className="w-12 shrink-0 text-right font-semibold text-assay">{e.rerank_score != null ? e.rerank_score.toFixed(2) : `#${i + 1}`}</span>
                </button>
            ))}
        </div>
    );
}

function EvidencePane({ e, n, onClose }: { e: Evidence | null; n: number | null; onClose: () => void }) {
    if (!e || !n) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center text-sm text-body">
                <Icon name="bbox" className="h-7 w-7 text-muted" />
                Click a citation to see the passage it came from.
            </div>
        );
    }
    const reranked = e.rerank_score !== null && e.rerank_score !== undefined;
    const score = reranked ? (e.rerank_score as number) : e.score;
    return (
        <div className="flex h-full flex-col gap-3.5 p-5">
            <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate text-sm font-semibold">[{n}] {e.title || e.source_name}</span>
                    <span className="text-xs text-body">
                        {e.source_name}{e.locator.page ? ` · page ${e.locator.page}${e.locator.total_pages ? ` of ${e.locator.total_pages}` : ''}` : ''}{e.locator.section ? ` · ${e.locator.section}` : ''}
                    </span>
                </div>
                <button onClick={onClose} className="text-body" aria-label="Close"><Icon name="dropped" className="h-5 w-5" /></button>
            </div>
            {reranked ? (
                <span className={clsx('w-fit rounded-full px-2.5 py-1 text-xs font-semibold', score >= 0.5 ? 'bg-assay text-white' : 'bg-bench text-conflict')}>
                    Relevance {score.toFixed(2)}
                </span>
            ) : (
                <span className="w-fit rounded-full bg-bench px-2.5 py-1 text-xs font-semibold text-body">Match #{n} · keyword search</span>
            )}
            <div className="flex-1 overflow-y-auto rounded-md bg-paper p-6">
                <div className="rounded border-2 border-assay bg-lime-wash px-3 py-2 font-prose text-[15px] leading-6 text-ink">
                    {e.snippet}
                </div>
            </div>
            {e.type === 'web' && (
                <p className="text-xs text-body">
                    Web page snapshot{typeof e.metadata?.fetched_at === 'string' ? ` taken ${new Date(e.metadata.fetched_at).toLocaleString()}` : ''}. Treated as a lower-trust source than your documents.
                </p>
            )}
            {e.locator.url && (
                <a href={e.locator.url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-[13px] font-semibold text-assay">
                    <Icon name="export" className="h-4 w-4" />Open the source page
                </a>
            )}
        </div>
    );
}

export function AskPage() {
    const { messages, sendMessage, cancelStream, isStreaming, clearMessages, useWeb, setUseWeb } = useChatStore();
    const [web, setWeb] = useState<{ mode: string; ready: boolean } | null>(null);
    useEffect(() => {
        api.get('/providers/runtime').then((r) => setWeb(r.data.web)).catch(() => setWeb(null));
    }, []);
    const [draft, setDraft] = useState('');
    const [selected, setSelected] = useState<{ msg: string; n: number } | null>(null);
    const endRef = useRef<HTMLDivElement>(null);

    const turns = useMemo(() => {
        const out: { q: Message; a?: Message }[] = [];
        messages.forEach((m) => {
            if (m.role === 'user') out.push({ q: m });
            else if (m.role === 'assistant' && out.length) out[out.length - 1].a = m;
        });
        return out;
    }, [messages]);

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    const selMsg = selected ? messages.find((m) => m.id === selected.msg) : null;
    const selEv = selMsg && selected ? selMsg.evidence?.[selected.n - 1] ?? null : null;

    function submit(text = draft) {
        const t = text.trim();
        if (!t || isStreaming) return;
        sendMessage(t);
        setDraft('');
    }

    return (
        <div className="flex h-full bg-paper">
            <div className="flex min-w-0 flex-1 flex-col">
                <div className="flex-1 overflow-y-auto">
                    <div className="mx-auto flex max-w-[760px] flex-col gap-12 px-6 py-9 lg:px-12">
                        {!turns.length && (
                            <div className="flex flex-col gap-6 pt-[12vh]">
                                <h1 className="font-display text-[44px] font-extrabold leading-[46px] tracking-[-0.03em]">
                                    Ask your documents.<br /><span className="text-body">Every sentence comes with its page.</span>
                                </h1>
                                <div className="flex flex-col gap-2">
                                    {SUGGESTIONS.map((s) => (
                                        <button key={s} onClick={() => submit(s)}
                                            className="flex items-center gap-3 rounded-xl border border-rule px-4 py-3 text-left text-[15px] hover:border-[#C9D0C4]">
                                            <Icon name="ask" className="h-[18px] w-[18px] shrink-0 text-assay" />{s}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {turns.map(({ q, a }) => (
                            <section key={q.id} className="flex flex-col gap-6">
                                <h2 className="font-display text-[30px] font-bold leading-9 tracking-[-0.02em]">{q.content}</h2>
                                {a && <StagePills m={a} />}
                                {a && <Answer m={a} onCite={(n) => setSelected({ msg: a.id, n })} />}
                                {a?.warnings?.length ? (
                                    <div className="flex flex-col gap-1 text-[13px] text-conflict">
                                        {a.warnings.map((w) => <span key={w} className="flex items-center gap-1.5"><Icon name="conflict" className="h-4 w-4" />{w}</span>)}
                                    </div>
                                ) : null}
                                {a && a.status === 'done' && (
                                    <div className="flex items-center gap-4 text-[13px] font-semibold">
                                        <span className="text-ink">Sources</span>
                                        <span className="flex items-center gap-1.5 text-assay"><Icon name="verify" className="h-4 w-4" strokeWidth={2} />{a.evidence?.length ?? 0} passages</span>
                                        {a.confidence && <span className={clsx(a.confidence === 'high' ? 'text-assay' : a.confidence === 'medium' ? 'text-conflict' : 'text-dropped')}>Confidence {a.confidence}</span>}
                                    </div>
                                )}
                                {a?.evidence && <Sources ev={a.evidence} selected={selected?.msg === a.id ? selected.n : null}
                                    onSelect={(n) => setSelected({ msg: a.id, n })} />}
                            </section>
                        ))}
                        <div ref={endRef} />
                    </div>
                </div>

                <div className="mx-auto w-full max-w-[760px] px-6 pb-6 lg:px-12">
                    <form onSubmit={(e) => { e.preventDefault(); submit(); }}
                        className="flex items-center gap-3 rounded-[14px] border border-[#D5DBD0] bg-paper py-2 pl-[18px] pr-2 focus-within:border-ink">
                        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={turns.length ? 'Ask a follow up' : 'Ask a question about your documents'}
                            className="flex-1 bg-transparent py-2 text-[15px] outline-none placeholder:text-muted" />
                        {web?.ready && (
                            <button type="button" onClick={() => setUseWeb(!useWeb)} aria-pressed={useWeb}
                                title={web.mode === 'auto' ? 'The web is also searched when documents have nothing' : 'Search the web for this question'}
                                className={clsx('flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium',
                                    useWeb ? 'bg-ink text-white' : 'bg-bench text-body')}>
                                <Icon name="web" className={clsx('h-4 w-4', useWeb && 'text-lime')} />Web
                            </button>
                        )}
                        {turns.length > 0 && !isStreaming && (
                            <button type="button" onClick={() => { clearMessages(); setSelected(null); }} className="text-xs text-body">New</button>
                        )}
                        {isStreaming ? (
                            <button type="button" onClick={cancelStream} className="flex h-10 items-center rounded-[10px] bg-bench px-3 text-sm font-medium">Stop</button>
                        ) : (
                            <button type="submit" disabled={!draft.trim()} aria-label="Ask"
                                className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-lime disabled:opacity-50">
                                <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="#0E1510" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" /></svg>
                            </button>
                        )}
                    </form>
                </div>
            </div>

            <aside className={clsx('hidden w-[440px] shrink-0 border-l border-rule bg-[#EEF1EA] xl:block', !turns.length && 'xl:hidden')}>
                <EvidencePane e={selEv} n={selected?.n ?? null} onClose={() => setSelected(null)} />
            </aside>
        </div>
    );
}
