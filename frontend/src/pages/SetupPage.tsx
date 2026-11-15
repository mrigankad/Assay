import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import clsx from 'clsx';
import toast from 'react-hot-toast';
import api from '@/services/api';
import { Icon } from '@/components/Icon';
import { providerService, providerLogo, type DetectedProvider } from '@/services/providers';

/** The model string a detected provider contributes as the workspace default. */
function defaultModel(p: DetectedProvider): string | null {
    if (p.kind === 'cli') return `${p.id}/`;
    if (p.id === 'ollama') {
        const m = p.models.find((x) => /-cloud$|:cloud$/.test(x)) ?? p.models[0];
        return m ? `ollama_chat/${m}` : null;
    }
    return p.models.find((m) => !/embed|rerank/i.test(m)) ?? null;
}

function describe(p: DetectedProvider) {
    if (p.id === 'claude_code') return 'Claude Code is signed in. Runs on your plan, personal use only.';
    if (p.id === 'codex_cli') return 'Codex CLI is signed in. Runs on your plan, personal use only.';
    if (p.id === 'gemini_cli') return 'Gemini CLI is signed in. Runs on your plan, personal use only.';
    if (p.id === 'ollama') {
        const cloud = p.models.filter((m) => /-cloud$|:cloud$/.test(m));
        return cloud.length ? `${cloud[0]} via your Ollama sign-in. Runs remotely.` : `${p.models.length} local models`;
    }
    return p.via.startsWith('env:') ? `Key found in ${p.via.slice(4).split('+')[0]}` : p.via;
}

const ADD_OPTIONS = [
    { title: 'Paste an API key', body: 'OpenAI, Anthropic, Gemini, Mistral and 40 more', logos: ['openai', 'anthropic', 'gemini'] },
    { title: 'Use a cloud account', body: 'AWS, Azure or Google login on this machine', logos: ['bedrock', 'azure', 'vertex_ai'] },
    { title: 'A gateway URL', body: 'OpenRouter, LiteLLM, any OpenAI-compatible', logos: ['openrouter', 'vercel_ai_gateway'] },
];

export function SetupPage() {
    const navigate = useNavigate();
    const [found, setFound] = useState<DetectedProvider[] | null>(null);
    const [choice, setChoice] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        providerService.detected(true).then((d) => {
            // Same order the router prefers: hosted keys, then enabled vendor CLIs, then Ollama.
            const rank = (p: DetectedProvider) => (p.kind === 'cli' ? 1 : p.id === 'ollama' ? 2 : p.kind === 'local' ? 3 : 0);
            const usable = d.filter((p) => p.enabled && p.caps.includes('chat') && defaultModel(p))
                .sort((a, b) => rank(a) - rank(b));
            setFound(usable);
            setChoice(usable[0]?.id ?? null);
        }).catch(() => setFound([]));
    }, []);

    const chosen = useMemo(() => found?.find((p) => p.id === choice) ?? null, [found, choice]);

    async function next() {
        if (!chosen) return navigate('/models');
        setSaving(true);
        try {
            await api.put('/providers/preferences', { default: defaultModel(chosen), roles: {} });
            toast.success(`Using ${chosen.name.replace(/ \(.*\)/, '')}`);
            navigate('/documents');
        } catch {
            toast.error('Only an admin can change the workspace model');
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="flex min-h-screen flex-col items-center gap-7 bg-bench px-6 py-10 text-ink">
            <div className="flex w-full max-w-[1360px] items-center justify-between">
                <div className="flex items-center gap-2.5">
                    <svg viewBox="0 0 32 32" className="h-[26px] w-[26px]"><path d="M16 3 L28 26 H4 Z" fill="#0E1510" /><rect x="7" y="17" width="18" height="4" rx="1" fill="#C6F432" /></svg>
                    <span className="font-display text-[21px] font-extrabold tracking-[-0.03em]">assay</span>
                </div>
                <ol className="hidden items-center gap-2.5 text-[13px] md:flex">
                    {['Model', 'Documents', 'First question'].map((s, i) => (
                        <li key={s} className={clsx('flex items-center gap-1.5', i ? 'text-body' : 'font-semibold')}>
                            <span className={clsx('flex h-[22px] w-[22px] items-center justify-center rounded-full text-xs',
                                i ? 'border border-[#C9D0C4]' : 'bg-ink text-lime')}>{i + 1}</span>{s}
                            {i < 2 && <span className="ml-2.5 h-px w-9 bg-[#C9D0C4]" />}
                        </li>
                    ))}
                </ol>
                <button onClick={() => navigate('/')} className="text-[13px] text-body">Skip setup</button>
            </div>

            <div className="flex w-full max-w-[1080px] flex-1 flex-col overflow-hidden rounded-3xl bg-paper md:flex-row">
                <div className="flex flex-col gap-[18px] bg-ink p-10 text-white md:w-[400px] md:shrink-0">
                    <img src="/brand/art/connect.webp" alt="" className="aspect-square w-full max-w-[320px] rounded-2xl object-cover" />
                    <h1 className="font-display text-[34px] font-extrabold leading-9 tracking-[-0.03em]">Connect a model</h1>
                    <p className="text-[15px] leading-[23px] text-[#B9C2BB]">
                        {found === null ? 'Looking around this machine…'
                            : found.length ? `Assay found ${found.length === 1 ? 'one model' : `${found.length} models`} you can use now. You can add more later and pick a model per agent role.`
                                : 'Nothing usable yet. Add a key, a cloud login or a gateway, then scan again.'}
                    </p>
                </div>

                <div className="flex flex-1 flex-col gap-3.5 p-10">
                    {!!found?.length && <span className="text-xs font-semibold text-body">Found on this machine</span>}
                    {found?.map((p) => {
                        const on = p.id === choice;
                        return (
                            <button key={p.id} onClick={() => setChoice(p.id)}
                                className={clsx('flex items-center gap-3.5 rounded-[14px] p-[18px] text-left transition',
                                    on ? 'border-2 border-ink' : 'border border-rule hover:border-[#C9D0C4]')}>
                                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-bench">
                                    <img src={providerLogo(p.id)} alt="" className="h-6 w-6" />
                                </span>
                                <span className="flex flex-1 flex-col gap-[3px]">
                                    <span className="text-base font-semibold">{p.id === 'claude_code' ? 'Your Claude login' : p.id === 'ollama' ? 'Ollama Cloud' : p.name}</span>
                                    <span className="text-[13px] text-body">{describe(p)}</span>
                                </span>
                                <span className={clsx('flex h-[22px] w-[22px] items-center justify-center rounded-full',
                                    on ? 'bg-ink' : 'border-[1.5px] border-[#C9D0C4]')}>
                                    {on && <Icon name="check" className="h-3 w-3 text-lime" strokeWidth={3} />}
                                </span>
                            </button>
                        );
                    })}

                    <span className="pt-2.5 text-xs font-semibold text-body">Or add one</span>
                    <div className="grid gap-2.5 sm:grid-cols-3">
                        {ADD_OPTIONS.map((o) => (
                            <button key={o.title} onClick={() => navigate('/models')}
                                className="flex flex-col gap-2.5 rounded-[14px] border border-rule p-4 text-left hover:border-[#C9D0C4]">
                                <span className="flex gap-1.5">{o.logos.map((l) => <img key={l} src={providerLogo(l)} alt="" className="h-[18px] w-[18px]" />)}</span>
                                <span className="text-sm font-semibold">{o.title}</span>
                                <span className="text-xs leading-[17px] text-body">{o.body}</span>
                            </button>
                        ))}
                    </div>

                    <div className="flex-1" />
                    <div className="flex justify-end">
                        <button onClick={next} disabled={saving || found === null}
                            className="flex h-11 items-center gap-2 rounded-xl bg-ink px-[18px] text-[15px] font-semibold text-white disabled:opacity-60">
                            {chosen ? `Continue with ${chosen.id === 'claude_code' ? 'Claude' : chosen.id === 'ollama' ? 'Ollama Cloud' : chosen.name.replace(/ \(.*\)/, '')}` : 'Open Models'}
                            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="#C6F432" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
