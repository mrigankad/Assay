import { useEffect, useState } from 'react';
import clsx from 'clsx';
import { Icon } from '@/components/Icon';
import { traceService, type TraceDetail, type TraceSummary } from '@/services/providers';

const secs = (ms?: number) => (ms ? `${(ms / 1000).toFixed(1)} s` : '-');
// Some timestamps come without a zone; they are UTC on the server.
const asUtc = (iso: string) => (/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
const when = (iso?: string) => (iso ? new Date(asUtc(iso)).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '');
const modelLabel = (m?: string) => (!m ? '-' : m.startsWith('claude_code/') ? 'Claude Code' : m.replace(/^ollama_chat\//, ''));

function Tile({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
    return (
        <div className={clsx('flex flex-1 flex-col gap-1 rounded-[14px] px-[18px] py-4', accent ? 'bg-lime' : 'bg-bench')}>
            <span className="text-xs text-body">{label}</span>
            <span className="font-display text-[26px] font-extrabold leading-8">{value}</span>
        </div>
    );
}

function Detail({ t }: { t: TraceDetail }) {
    const total = t.total_latency_ms || 1;
    const calls = t.tool_calls ?? [];
    const cites = t.extra?.citations ?? [];
    const resolved = cites.filter((c) => c.resolved).length;
    const tokens = (t.prompt_tokens ?? 0) + (t.completion_tokens ?? 0);

    function download() {
        const blob = new Blob([JSON.stringify(t, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `assay-trace-${t.trace_id}.json`;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    return (
        <div className="flex flex-col gap-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex max-w-[720px] flex-col gap-2">
                    <span className="break-all text-[13px] text-body">Run {t.trace_id} · {when(t.created_at)}</span>
                    <h2 className="font-display text-[28px] font-bold leading-8 tracking-[-0.02em]">{t.query}</h2>
                </div>
                <button onClick={download} className="flex h-9 items-center gap-2 rounded-[10px] border border-[#D5DBD0] px-3.5 text-sm font-medium">
                    <Icon name="export" className="h-4 w-4" />Export JSON
                </button>
            </div>

            <div className="flex flex-wrap gap-2.5">
                <Tile label="Duration" value={secs(t.total_latency_ms)} />
                <Tile label="Model" value={modelLabel(t.model)} />
                <Tile label="Tokens" value={tokens ? tokens.toLocaleString() : 'n/a'} />
                <Tile label="Citations resolved" value={cites.length ? `${resolved} / ${cites.length}` : '-'} accent={!!cites.length && resolved === cites.length} />
            </div>

            <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0"><div className="flex min-w-[640px] flex-col text-[13px]">
                <div className="flex items-center border-b border-ink pb-2.5 text-xs font-semibold text-body">
                    <span className="w-[230px] shrink-0">Step</span>
                    <span className="w-[120px] shrink-0">Where</span>
                    <span className="flex flex-1 justify-between pr-4"><span>0 s</span><span>{secs(total)}</span></span>
                    <span className="w-[70px] shrink-0 text-right">Results</span>
                </div>
                <div className="flex items-center border-b border-[#EEF1EA] py-[11px]">
                    <span className="w-[230px] shrink-0 font-semibold">Route · {t.extra?.route_method ?? 'rules'} · {t.intent?.toLowerCase()}</span>
                    <span className="w-[120px] shrink-0 text-body">planner</span>
                    <span className="flex flex-1 pr-4" />
                    <span className="w-[70px] shrink-0 text-right text-body">{t.plan?.steps?.length ?? 0} steps</span>
                </div>
                {calls.map((c, i) => (
                    <div key={i} className="flex items-center border-b border-[#EEF1EA] py-[11px]">
                        <span className="flex w-[230px] shrink-0 items-center gap-2 font-semibold">
                            <Icon name={c.tool.includes('web') ? 'web' : c.tool.includes('data') ? 'table' : 'search'} className="h-4 w-4 text-body" />
                            {c.tool}
                        </span>
                        <span className="w-[120px] shrink-0 text-body">{c.backend ?? '-'}</span>
                        <span className="flex flex-1 pr-4">
                            <span className={clsx('h-2.5 rounded-[3px]', c.status === 'ok' ? 'bg-ink' : 'bg-dropped')}
                                style={{ width: `${Math.max(2, Math.min(100, ((c.latency_ms ?? 0) / total) * 100))}%` }} />
                        </span>
                        <span className="w-[70px] shrink-0 text-right text-body">{c.result_count ?? '-'}</span>
                    </div>
                ))}
                <div className="flex items-center bg-[#F7FCE8] py-[11px]">
                    <span className="flex w-[230px] shrink-0 items-center gap-2 font-semibold"><Icon name="ask" className="h-4 w-4 text-body" />Write + check citations</span>
                    <span className="w-[120px] shrink-0 text-body">{modelLabel(t.model)}</span>
                    <span className="flex flex-1 pr-4">
                        <span className="h-2.5 rounded-[3px] border border-ink bg-lime"
                            style={{ width: `${Math.max(2, 100 - (calls.reduce((a, c) => a + (c.latency_ms ?? 0), 0) / total) * 100)}%`, marginLeft: 'auto' }} />
                    </span>
                    <span className="w-[70px] shrink-0 text-right text-body">{t.evidence_count ?? 0} used</span>
                </div>
            </div></div>

            <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
                <div className="flex flex-col gap-2.5 rounded-[14px] border border-rule p-[18px] text-[13px] leading-5">
                    <span className="text-xs font-semibold text-body">Plan</span>
                    {t.plan?.reasoning && <span>{t.plan.reasoning}</span>}
                    {(t.plan?.steps ?? []).map((s) => (
                        <span key={s.id}><b>{s.id}</b> · {s.tool} · {s.goal}{s.alternate_queries?.length ? ` (+${s.alternate_queries.length} phrasings)` : ''}</span>
                    ))}
                    {(t.extra?.warnings ?? []).map((w) => (
                        <span key={w} className="flex items-center gap-1.5 text-conflict"><Icon name="conflict" className="h-4 w-4" />{w}</span>
                    ))}
                    {cites.some((c) => !c.resolved) && (
                        <span className="flex items-center gap-1.5 text-dropped"><Icon name="dropped" className="h-4 w-4" />
                            {cites.filter((c) => !c.resolved).length} citation(s) pointed nowhere and were removed</span>
                    )}
                </div>
                <div className="flex flex-col gap-2.5 rounded-[14px] bg-bench p-[18px] text-[13px] leading-5">
                    <span className="text-xs font-semibold text-body">Reproducibility</span>
                    <span>Knowledge backend <b>{t.extra?.backend ?? 'local'}</b></span>
                    <span>Session <b>{t.session_id ?? '-'}</b></span>
                    <span>Confidence <b>{t.confidence ?? '-'}</b></span>
                </div>
            </div>
        </div>
    );
}

export function AuditPage() {
    const [list, setList] = useState<TraceSummary[] | null>(null);
    const [sel, setSel] = useState<TraceDetail | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [showDetail, setShowDetail] = useState(false);   // phones: list or detail, one at a time

    useEffect(() => {
        traceService.list().then((l) => {
            setList(l);
            if (l[0]) traceService.get(l[0].trace_id).then(setSel).catch(() => undefined);
        }).catch(() => setError('Could not load the audit log'));
    }, []);

    return (
        <div className="flex h-full bg-paper">
            <aside className={clsx('w-full shrink-0 flex-col border-rule lg:flex lg:w-[300px] lg:border-r', showDetail ? 'hidden' : 'flex')}>
                <div className="px-5 pb-3 pt-9">
                    <span className="text-[13px] text-body">Workspace · Audit log</span>
                    <h1 className="font-display text-[28px] font-bold">Answers</h1>
                </div>
                <div className="flex-1 overflow-y-auto">
                    {error && <p className="px-5 text-sm text-dropped">{error}</p>}
                    {list?.length === 0 && <p className="px-5 text-sm text-body">No questions asked yet.</p>}
                    {list?.map((t) => (
                        <button key={t.trace_id} onClick={() => { setShowDetail(true); traceService.get(t.trace_id).then(setSel); }}
                            className={clsx('flex w-full flex-col gap-1 border-b border-[#EEF1EA] px-5 py-3 text-left',
                                sel?.trace_id === t.trace_id ? 'bg-[#F7FCE8]' : 'hover:bg-bench')}>
                            <span className="line-clamp-2 text-sm font-medium">{t.query}</span>
                            <span className="text-xs text-body">{when(t.created_at)} · {secs(t.total_latency_ms)} · {t.evidence_count ?? 0} sources</span>
                        </button>
                    ))}
                </div>
            </aside>
            <div className={clsx('min-w-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:block lg:px-12 lg:py-9', showDetail ? 'block' : 'hidden')}>
                <button onClick={() => setShowDetail(false)} className="mb-4 flex items-center gap-1.5 text-sm font-medium text-body lg:hidden">
                    <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M10 3 5 8l5 5" /></svg>
                    All answers
                </button>
                {sel ? <Detail t={sel} /> : (
                    <div className="flex h-full items-center justify-center text-sm text-body">
                        {list === null ? 'Loading…' : 'Pick an answer to see how it was made.'}
                    </div>
                )}
            </div>
        </div>
    );
}
