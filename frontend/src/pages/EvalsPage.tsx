import { useEffect, useState } from 'react';
import clsx from 'clsx';
import toast from 'react-hot-toast';
import api from '@/services/api';
import { Icon } from '@/components/Icon';

interface Dataset { name: string; questions: number }
interface Run {
    run_id: string; dataset: string; model?: string | null; created_at: string; cases: number;
    hit_rate: number; mrr: number; answer_substring_recall?: number | null; citation_rate?: number | null;
    faithfulness?: number | null; p50_total_ms: number; local_compute?: string;
}

const pct = (v?: number | null) => (v === null || v === undefined ? '-' : v.toFixed(2));
const modelName = (m?: string | null) => (!m ? 'unknown' : m.startsWith('claude_code/') ? 'Claude login' : m.replace(/^ollama_chat\//, ''));
const when = (stamp: string) => {
    const m = stamp.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/);
    return m ? new Date(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:00Z`).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : stamp;
};

function Bar({ v, strong }: { v?: number | null; strong?: boolean }) {
    return (
        <span className="flex flex-1 items-center gap-2.5 pr-5">
            <span className="h-2 flex-1 rounded-full bg-rule">
                <span className={clsx('block h-2 rounded-full', strong ? 'bg-ink' : 'bg-body')} style={{ width: `${Math.round((v ?? 0) * 100)}%` }} />
            </span>
            <b className="w-9 text-right">{pct(v)}</b>
        </span>
    );
}

export function EvalsPage() {
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [dataset, setDataset] = useState('sample');
    const [runs, setRuns] = useState<Run[] | null>(null);
    const [running, setRunning] = useState(false);

    async function load() {
        const [d, r] = await Promise.all([api.get('/evaluations/datasets'), api.get('/evaluations/runs')]);
        setDatasets(d.data.datasets);
        if (d.data.datasets[0] && !d.data.datasets.some((x: Dataset) => x.name === dataset)) setDataset(d.data.datasets[0].name);
        setRuns(r.data.runs);
    }
    useEffect(() => { load().catch(() => setRuns([])); }, []);

    async function run() {
        setRunning(true);
        try {
            await api.post('/evaluations/run', { dataset, top_k: 8 }, { timeout: 1800000 });
            toast.success('Eval finished');
            await load();
        } catch (e) {
            const s = (e as { response?: { status?: number } }).response?.status;
            toast.error(s === 403 ? 'Only an admin can run evals' : 'Eval run failed');
        } finally {
            setRunning(false);
        }
    }

    const best = runs?.length ? runs.reduce((a, b) => ((b.answer_substring_recall ?? b.hit_rate) > (a.answer_substring_recall ?? a.hit_rate) ? b : a)) : null;
    const ds = datasets.find((d) => d.name === dataset);

    return (
        <div className="h-full overflow-y-auto bg-paper">
            <div className="mx-auto flex max-w-[1180px] flex-col gap-6 px-6 py-9 lg:px-12">
                <header className="flex flex-wrap items-end justify-between gap-4">
                    <div className="flex flex-col gap-2">
                        <span className="text-[13px] text-body">Workspace · Evals · questions with known answers</span>
                        <h1 className="font-display text-[34px] font-bold leading-none">Which setup answers best?</h1>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="flex rounded-[10px] bg-bench p-[3px] text-[13px] font-medium" role="radiogroup" aria-label="Dataset">
                            {datasets.map((d) => (
                                <button key={d.name} role="radio" aria-checked={d.name === dataset} onClick={() => setDataset(d.name)}
                                    className={clsx('rounded-lg px-3 py-1.5', d.name === dataset ? 'bg-ink text-white' : 'text-body')}>
                                    {d.name} · {d.questions}
                                </button>
                            ))}
                        </div>
                        <button onClick={run} disabled={running || !ds}
                            className="flex h-9 items-center gap-2 rounded-[10px] bg-ink px-3.5 text-sm font-medium text-white disabled:opacity-60">
                            <Icon name="plus" className="h-4 w-4 text-lime" strokeWidth={2} />
                            {running ? `Running ${ds?.questions ?? ''} questions…` : 'New run'}
                        </button>
                    </div>
                </header>

                {runs && runs.length === 0 && !running && (
                    <div className="flex items-center gap-6 rounded-[18px] bg-ink p-6 text-white">
                        <img src="/brand/art/evals.webp" alt="" className="h-32 w-32 shrink-0 rounded-xl object-cover" />
                        <div className="flex flex-col gap-2">
                            <span className="font-display text-2xl font-bold">No runs yet</span>
                            <span className="max-w-[560px] text-sm leading-[21px] text-[#B9C2BB]">
                                An eval asks every question in a dataset with your current models and checks the answers and sources against what's expected.
                                Run one, switch models, run again, and compare here. Datasets live in <b className="text-white">evals/datasets</b>.
                            </span>
                        </div>
                    </div>
                )}

                {!!runs?.length && (
                    <div className="flex flex-col text-sm">
                        <div className="flex items-center border-b border-ink pb-2.5 text-xs font-semibold text-body">
                            <span className="w-[240px] shrink-0">Run</span>
                            <span className="flex-1">Found the right source</span>
                            <span className="flex-1">Answer has the expected fact</span>
                            <span className="w-[90px] shrink-0">Cited</span>
                            <span className="w-[80px] shrink-0 text-right">p50 time</span>
                        </div>
                        {runs.map((r) => (
                            <div key={r.run_id} className={clsx('flex items-center border-b border-[#EEF1EA] py-4', r === best && runs.length > 1 && 'bg-[#F7FCE8]')}>
                                <span className="flex w-[240px] shrink-0 flex-col gap-[3px]">
                                    <span className="flex items-center gap-2 font-semibold">{modelName(r.model)}
                                        {r === best && runs.length > 1 && <span className="rounded-full bg-ink px-[7px] py-0.5 text-[11px] text-lime">best</span>}</span>
                                    <span className="text-xs text-body">{r.dataset} · {r.cases} questions · {when(r.created_at)}</span>
                                </span>
                                <Bar v={r.hit_rate} strong={r === best} />
                                <Bar v={r.answer_substring_recall} strong={r === best} />
                                <span className="w-[90px] shrink-0 font-semibold">{r.citation_rate === null || r.citation_rate === undefined ? '-' : `${Math.round(r.citation_rate * 100)}%`}</span>
                                <span className="w-[80px] shrink-0 text-right text-body">{(r.p50_total_ms / 1000).toFixed(1)} s</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
