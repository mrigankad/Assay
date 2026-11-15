import { useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';
import { Icon } from '@/components/Icon';
import {
    providerService, providerLogo, providerIdFromModel, ROLE_ORDER,
    type CatalogProvider, type DetectedProvider, type RoleAssignment,
} from '@/services/providers';

const ROLE_META: Record<string, { label: string; icon: string; hint: string }> = {
    planner: { label: 'Planner', icon: 'planner', hint: 'Splits a question into hops' },
    search: { label: 'Search', icon: 'search', hint: 'Rewrites queries, picks sources' },
    expert: { label: 'Experts', icon: 'expert', hint: 'Domain personas' },
    verifier: { label: 'Verifier', icon: 'verify', hint: 'Checks every claim' },
    browser: { label: 'Browser', icon: 'web', hint: 'Reads the web when asked' },
    vision: { label: 'Vision parse', icon: 'bbox', hint: 'Tables, charts, scans' },
    synthesis: { label: 'Writer', icon: 'ask', hint: 'Writes the cited answer' },
    embed: { label: 'Embeddings', icon: 'collection', hint: 'Vectors for search' },
    rerank: { label: 'Rerank', icon: 'reports', hint: 'Orders evidence' },
};

const KIND_LABEL: Record<string, string> = {
    hyperscaler: 'Clouds', lab: 'Model labs', inference: 'Inference APIs',
    aggregator: 'Gateways', local: 'Local runtimes', cli: 'CLI logins',
};

function Logo({ id, size = 34, dark = false }: { id: string | null; size?: number; dark?: boolean }) {
    return (
        <span className={clsx('flex shrink-0 items-center justify-center rounded-[9px]', dark ? 'bg-ink' : 'bg-bench')}
            style={{ width: size, height: size }}>
            {id && <img src={providerLogo(id)} alt="" className={clsx(dark && 'invert')}
                style={{ width: size * 0.55, height: size * 0.55 }} />}
        </span>
    );
}

const CLI_NAMES: Record<string, string> = { claude_code: 'Claude Code', codex_cli: 'Codex CLI', gemini_cli: 'Gemini CLI' };

/** "claude_code/" -> "Claude Code · default model", "ollama_chat/gpt-oss:20b-cloud" -> "gpt-oss:20b-cloud" */
function modelLabel(model: string) {
    const [prefix, ...rest] = model.split('/');
    const name = rest.join('/');
    if (CLI_NAMES[prefix]) return `${CLI_NAMES[prefix]} · ${name || 'default model'}`;
    return name || model;
}

const MISSING_HINT: Record<string, string> = {
    embed: 'Needs an embedding key (Gemini, OpenAI, Jina…)',
    rerank: 'Optional: answers keep fusion order without a reranker',
};

function viaLabel(via: string) {
    if (via.startsWith('env:')) return via.slice(4).split('+')[0];
    if (via.startsWith('file:')) return via.slice(5);
    if (via.startsWith('port:')) return `localhost:${via.slice(5)}`;
    if (via.startsWith('cli:')) return `${via.slice(4)} on PATH`;
    return via;
}

export function ModelsPage() {
    const [found, setFound] = useState<DetectedProvider[]>([]);
    const [catalog, setCatalog] = useState<CatalogProvider[]>([]);
    const [roles, setRoles] = useState<Record<string, RoleAssignment>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [tests, setTests] = useState<Record<string, string>>({});
    const [showAll, setShowAll] = useState(false);

    async function load(refresh = false) {
        setLoading(true);
        setError(null);
        try {
            const [d, c, r] = await Promise.all([providerService.detected(refresh), providerService.catalog(), providerService.roles()]);
            setFound(d); setCatalog(c); setRoles(r);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Could not reach the Assay API');
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => { load(); }, []);

    async function test(role: string) {
        setTests((t) => ({ ...t, [role]: 'Testing…' }));
        try {
            const r = await providerService.test(role);
            setTests((t) => ({ ...t, [role]: r.dimension ? `${r.dimension}-d · ${r.latency_ms} ms` : `${r.latency_ms} ms` }));
        } catch {
            setTests((t) => ({ ...t, [role]: 'Failed' }));
        }
    }

    const foundIds = useMemo(() => new Set(found.map((f) => f.id)), [found]);
    const notFound = useMemo(() => catalog.filter((c) => !foundIds.has(c.id)), [catalog, foundIds]);
    const grouped = useMemo(() => {
        const g: Record<string, CatalogProvider[]> = {};
        notFound.forEach((p) => { (g[p.kind] ??= []).push(p); });
        return g;
    }, [notFound]);

    return (
        <div className="h-full overflow-y-auto bg-paper">
            <div className="mx-auto flex max-w-[1180px] flex-col gap-8 px-6 py-9 lg:px-12">
                <header className="flex flex-wrap items-end justify-between gap-4">
                    <div className="flex flex-col gap-2">
                        <span className="text-[13px] text-body">Workspace · Models</span>
                        <h1 className="font-display text-[34px] font-bold leading-none text-ink">Connections and roles</h1>
                    </div>
                    <button onClick={() => load(true)} disabled={loading}
                        className="flex h-9 items-center gap-2 rounded-[10px] bg-ink px-3.5 text-sm font-medium text-white disabled:opacity-60">
                        <Icon name="refresh" className={clsx('h-4 w-4 text-lime', loading && 'animate-spin')} />
                        Scan again
                    </button>
                </header>

                {error && (
                    <div className="rounded-xl border border-dropped/30 bg-dropped/5 px-4 py-3 text-sm text-dropped">{error}</div>
                )}

                <div className="grid gap-7 lg:grid-cols-[440px_1fr]">
                    {/* Connections found on this machine */}
                    <section className="flex flex-col gap-2">
                        <span className="pb-1 text-xs font-semibold text-body">
                            Found on this machine · {found.filter((f) => f.enabled).length} ready
                        </span>
                        {found.map((p) => (
                            <div key={p.id} className="flex items-center gap-3 rounded-xl border border-rule px-4 py-3.5">
                                <Logo id={p.id} dark={p.kind === 'local'} />
                                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                                    <span className="truncate text-sm font-semibold text-ink">{p.name}</span>
                                    <span className="truncate text-xs text-body">
                                        {viaLabel(p.via)}{p.models.length ? ` · ${p.models.length} model${p.models.length > 1 ? 's' : ''}` : ''}
                                    </span>
                                </div>
                                {p.enabled
                                    ? <span className="flex items-center gap-1 text-xs font-semibold text-assay"><Icon name="check" className="h-3.5 w-3.5" />Ready</span>
                                    : <span className="flex items-center gap-1 text-xs font-semibold text-conflict" title={p.risk ?? ''}><Icon name="lock" className="h-3.5 w-3.5" />Opt in</span>}
                            </div>
                        ))}
                        {!loading && found.length <= 1 && (
                            <p className="rounded-xl bg-bench px-4 py-3 text-sm text-body">
                                Nothing found yet. Set an API key such as <b>OPENAI_API_KEY</b>, sign in to a cloud
                                (<b>aws sso login</b>, <b>az login</b>, <b>gcloud auth application-default login</b>), or start Ollama, LM Studio or vLLM, then scan again.
                            </p>
                        )}
                        <button onClick={() => setShowAll((v) => !v)}
                            className="flex h-11 items-center justify-center gap-2 rounded-xl border border-dashed border-[#C9D0C4] text-[13px] text-body">
                            <Icon name="plus" className="h-4 w-4" />
                            {showAll ? 'Hide' : `Connect one of ${notFound.length} more providers`}
                        </button>
                    </section>

                    {/* Role routing */}
                    <section className="flex min-w-0 flex-col gap-2 rounded-2xl bg-bench p-5">
                        <div className="flex items-center justify-between pb-1.5">
                            <span className="text-xs font-semibold text-body">Model per agent role · auto</span>
                            <span className="text-xs text-body">Override with ASSAY_MODEL_&lt;ROLE&gt;</span>
                        </div>
                        {ROLE_ORDER.map((role) => {
                            const meta = ROLE_META[role];
                            const a = roles[role];
                            const isVerifier = role === 'verifier';
                            return (
                                <div key={role} className={clsx('flex items-center gap-3 rounded-[10px] bg-paper px-3.5 py-2.5',
                                    isVerifier && 'ring-[1.5px] ring-assay')}>
                                    <Icon name={meta.icon} className={clsx('h-[18px] w-[18px]', isVerifier ? 'text-assay' : 'text-ink')} />
                                    <span className="w-[108px] shrink-0 text-sm font-semibold text-ink">{meta.label}</span>
                                    <Logo id={providerIdFromModel(a?.model)} size={22} />
                                    <span className={clsx('min-w-0 flex-1 truncate text-[13px]', a?.model ? 'text-ink' : role === 'rerank' ? 'text-body' : 'text-dropped')}
                                        title={a?.error ?? a?.model ?? ''}>
                                        {a?.model ? modelLabel(a.model) : loading ? '…' : (MISSING_HINT[role] ?? 'No model available')}
                                    </span>
                                    <button onClick={() => test(role)} disabled={!a?.model}
                                        className="shrink-0 text-xs font-semibold text-assay disabled:text-muted">
                                        {tests[role] ?? 'Test'}
                                    </button>
                                </div>
                            );
                        })}
                    </section>
                </div>

                {showAll && (
                    <section className="flex flex-col gap-6">
                        {Object.entries(grouped).map(([kind, items]) => (
                            <div key={kind} className="flex flex-col gap-3 border-t border-ink pt-4">
                                <div className="flex items-baseline gap-2">
                                    <h2 className="font-display text-xl font-bold text-ink">{KIND_LABEL[kind] ?? kind}</h2>
                                    <span className="text-xs text-body">{items.length}</span>
                                </div>
                                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                                    {items.map((p) => (
                                        <div key={p.id} className="flex items-start gap-3 rounded-xl border border-rule p-3.5">
                                            <Logo id={p.id} size={30} />
                                            <div className="flex min-w-0 flex-col gap-1">
                                                <span className="text-sm font-semibold text-ink">{p.name}</span>
                                                <span className="text-xs leading-[17px] text-body">
                                                    {p.port && !p.env.length ? `Start it on localhost:${p.port}` :
                                                        p.env.length ? <>Set <b className="text-ink">{p.env[0].join(' + ')}</b></> :
                                                            p.risk ? 'Install the CLI and sign in, then opt in' : 'Built in'}
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </section>
                )}
            </div>
        </div>
    );
}
