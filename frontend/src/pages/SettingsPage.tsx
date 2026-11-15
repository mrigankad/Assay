import { useEffect, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import toast from 'react-hot-toast';
import api from '@/services/api';
import { Icon } from '@/components/Icon';
import { providerLogo, providerService, type CatalogProvider } from '@/services/providers';

interface Runtime {
    local_compute: boolean; scan_local: boolean; enabled_clis: string[]; blocked: string[];
    default_visibility: string; acl_enforcement: boolean; auth_mode: string; knowledge_backend: string;
    web?: { mode: string; search_backend: string | null; ready: boolean };
}
interface Methods { password: boolean; entra: { enabled: boolean; tenant_id?: string | null }; oidc: { enabled: boolean; issuer?: string | null }; signup_open: boolean }
interface Prefs { default?: string | null; roles?: Record<string, string>; blocked?: string[] }

function Status({ on, label }: { on: boolean; label?: string }) {
    return (
        <span className={clsx('flex shrink-0 items-center gap-1.5 text-[13px] font-semibold', on ? 'text-assay' : 'text-body')}>
            <span className={clsx('h-2 w-2 rounded-full', on ? 'bg-assay' : 'bg-[#C9D0C4]')} />{label ?? (on ? 'On' : 'Off')}
        </span>
    );
}

function Row({ icon, title, body, right }: { icon?: React.ReactNode; title: string; body: React.ReactNode; right?: React.ReactNode }) {
    return (
        <div className="flex items-center gap-3.5 border-b border-[#EEF1EA] px-[18px] py-3.5 last:border-b-0">
            {icon}
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="text-sm font-semibold">{title}</span>
                <span className="text-[13px] text-body">{body}</span>
            </div>
            {right}
        </div>
    );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section className="flex flex-col gap-3">
            <h2 className="text-[13px] font-semibold text-body">{title}</h2>
            <div className="flex flex-col rounded-[14px] border border-rule">{children}</div>
        </section>
    );
}

/** Searchable provider picker (custom, no native select). */
function ProviderPicker({ options, onPick }: { options: CatalogProvider[]; onPick: (id: string) => void }) {
    const [open, setOpen] = useState(false);
    const [q, setQ] = useState('');
    const ref = useRef<HTMLDivElement>(null);
    useEffect(() => {
        const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
        document.addEventListener('mousedown', close);
        return () => document.removeEventListener('mousedown', close);
    }, []);
    const shown = options.filter((o) => o.name.toLowerCase().includes(q.toLowerCase())).slice(0, 8);
    return (
        <div ref={ref} className="relative">
            <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
                className="flex h-8 items-center gap-1.5 rounded-full border border-dashed border-[#C9D0C4] px-3 text-[13px] text-body">
                <Icon name="plus" className="h-3.5 w-3.5" strokeWidth={2} />Add provider
            </button>
            {open && (
                <div role="listbox" className="absolute right-0 z-20 mt-1.5 w-72 rounded-xl border border-rule bg-paper p-1.5 shadow-[0_8px_24px_rgba(14,21,16,0.08)]">
                    <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search providers"
                        className="mb-1 h-9 w-full rounded-lg bg-bench px-3 text-sm outline-none" />
                    {shown.map((o) => (
                        <button key={o.id} role="option" aria-selected={false} onClick={() => { onPick(o.id); setOpen(false); setQ(''); }}
                            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-bench">
                            <img src={providerLogo(o.id)} alt="" className="h-4 w-4" />{o.name}
                        </button>
                    ))}
                    {!shown.length && <p className="px-2.5 py-2 text-sm text-body">No match</p>}
                </div>
            )}
        </div>
    );
}

export function SettingsPage() {
    const [rt, setRt] = useState<Runtime | null>(null);
    const [methods, setMethods] = useState<Methods | null>(null);
    const [prefs, setPrefs] = useState<Prefs>({});
    const [catalog, setCatalog] = useState<CatalogProvider[]>([]);

    async function load() {
        const [r, m, p, c] = await Promise.all([
            api.get<Runtime>('/providers/runtime'), api.get<Methods>('/auth/methods'),
            api.get<Prefs>('/providers/preferences'), providerService.catalog(),
        ]);
        setRt(r.data); setMethods(m.data); setPrefs(p.data); setCatalog(c);
    }
    useEffect(() => { load().catch(() => toast.error('Could not load settings')); }, []);

    const blocked = prefs.blocked ?? [];
    const byId = useMemo(() => Object.fromEntries(catalog.map((c) => [c.id, c])), [catalog]);

    async function saveBlocked(next: string[]) {
        try {
            const r = await api.put<Prefs>('/providers/preferences', { ...prefs, roles: prefs.roles ?? {}, blocked: next });
            setPrefs(r.data);
            toast.success('Saved. Applies to the next question.');
            load();
        } catch {
            toast.error('Only an admin can change this');
        }
    }

    const env = (k: string) => <span className="rounded bg-bench px-1.5 py-0.5 text-[12px] font-medium text-ink">{k}</span>;

    return (
        <div className="h-full overflow-y-auto bg-paper">
            <div className="mx-auto flex max-w-[880px] flex-col gap-7 px-6 py-9 lg:px-12">
                <div className="flex flex-col gap-2">
                    <span className="text-[13px] text-body">Workspace · Settings</span>
                    <h1 className="font-display text-[34px] font-bold leading-none">Settings</h1>
                </div>

                <Section title="Sign-in methods">
                    <Row icon={<Icon name="ask" className="h-5 w-5" />} title="Email and password"
                        body={methods?.signup_open ? 'Anyone can sign up (ALLOW_SIGNUP=true)' : 'Built in. New people join by invite.'}
                        right={<Status on={!!methods?.password} />} />
                    <Row icon={<svg viewBox="0 0 24 24" className="h-5 w-5"><rect x="2" y="2" width="9.5" height="9.5" fill="#F25022" /><rect x="12.5" y="2" width="9.5" height="9.5" fill="#7FBA00" /><rect x="2" y="12.5" width="9.5" height="9.5" fill="#00A4EF" /><rect x="12.5" y="12.5" width="9.5" height="9.5" fill="#FFB900" /></svg>}
                        title="Microsoft Entra ID"
                        body={methods?.entra.enabled ? `Tenant ${methods.entra.tenant_id}` : <>Set {env('AUTH_MODE=both')}, {env('ENTRA_TENANT_ID')} and {env('ENTRA_CLIENT_ID')}</>}
                        right={<Status on={!!methods?.entra.enabled} label={methods?.entra.enabled ? 'Connected' : 'Not set up'} />} />
                    <Row icon={<Icon name="lock" className="h-5 w-5" />} title="Any OpenID Connect provider"
                        body={methods?.oidc.enabled ? methods.oidc.issuer : <>Okta, Google, Keycloak, Authentik: set {env('OIDC_ISSUER')} and {env('OIDC_CLIENT_ID')}</>}
                        right={<Status on={!!methods?.oidc.enabled} label={methods?.oidc.enabled ? 'Configured' : 'Not set up'} />} />
                </Section>

                <Section title="Who sees what">
                    <Row title="New documents are visible to"
                        body={<>{rt?.default_visibility === 'private' ? 'Only the uploader' : rt?.default_visibility === 'public' ? 'Everyone, including anonymous chat' : 'Everyone in the workspace'} · change with {env('DEFAULT_DOCUMENT_VISIBILITY')}</>}
                        right={<span className="rounded-full bg-bench px-2.5 py-1 text-[13px] font-semibold capitalize">{rt?.default_visibility ?? '…'}</span>} />
                    <Row title="Access checks on every answer"
                        body="Answers only use documents the person asking can open, including permissions synced from SharePoint and Drive."
                        right={<Status on={!!rt?.acl_enforcement} />} />
                </Section>

                <Section title="Privacy">
                    <Row icon={<Icon name="airgap" className="h-5 w-5" />} title="Keep inference off this machine"
                        body={<>{rt?.local_compute ? 'Local models may run here.' : 'No local model weights; cloud and login-based models only.'} Set with {env('ASSAY_LOCAL_COMPUTE')}</>}
                        right={<Status on={rt ? !rt.local_compute : false} />} />
                    <Row icon={<Icon name="web" className="h-5 w-5" />} title="Web search"
                        body={rt?.web?.mode === 'off' || !rt?.web
                            ? <>Off. Set {env('WEB_MODE=ask')} and a search key ({env('TAVILY_API_KEY')}, {env('BRAVE_API_KEY')}, {env('EXA_API_KEY')} or {env('SEARXNG_URL')})</>
                            : !rt.web.search_backend
                                ? <>Mode {rt.web.mode}, but no search backend: set {env('TAVILY_API_KEY')} or {env('SEARXNG_URL')}</>
                                : <>{rt.web.mode === 'auto' ? 'When asked, and when documents have nothing' : 'Only when someone ticks Web on a question'} · {rt.web.search_backend} · pages are snapshotted, robots.txt respected, read-only</>}
                        right={<Status on={!!rt?.web?.ready} label={rt?.web?.ready ? rt.web.mode === 'auto' ? 'Auto' : 'Ask' : 'Off'} />} />
                    <Row icon={<Icon name="models" className="h-5 w-5" />} title="Vendor CLI logins"
                        body={rt?.enabled_clis.length ? `Enabled: ${rt.enabled_clis.map((c) => byId[c]?.name.replace(/ \(.*\)/, '') ?? c).join(', ')} · personal use only` : 'None enabled'}
                        right={<Status on={!!rt?.enabled_clis.length} />} />
                    <div className="flex flex-col gap-3 px-[18px] py-3.5">
                        <div className="flex items-center gap-3.5">
                            <Icon name="dropped" className="h-5 w-5 text-dropped" />
                            <div className="flex flex-1 flex-col gap-0.5">
                                <span className="text-sm font-semibold">Never send document text to</span>
                                <span className="text-[13px] text-body">Skipped for every role, even if set as the default.</span>
                            </div>
                            <ProviderPicker options={catalog.filter((c) => !blocked.includes(c.id) && c.id !== 'builtin')}
                                onPick={(id) => saveBlocked([...blocked, id])} />
                        </div>
                        {blocked.length > 0 && (
                            <div className="flex flex-wrap gap-2 pl-[34px]">
                                {blocked.map((b) => (
                                    <span key={b} className="flex items-center gap-1.5 rounded-full bg-bench py-1 pl-2.5 pr-1.5 text-[13px]">
                                        <img src={providerLogo(b)} alt="" className="h-3.5 w-3.5" />{byId[b]?.name ?? b}
                                        <button onClick={() => saveBlocked(blocked.filter((x) => x !== b))} aria-label={`Unblock ${b}`} className="text-body hover:text-dropped">
                                            <Icon name="dropped" className="h-3.5 w-3.5" />
                                        </button>
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>
                </Section>
            </div>
        </div>
    );
}
