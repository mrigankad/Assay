import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import api from '@/services/api';
import { authService } from '@/services';
import { useAuthStore } from '@/stores/authStore';
import { Icon } from '@/components/Icon';

interface Methods {
    password: boolean;
    first_run: boolean;
    signup_open: boolean;
}

function AssayMark({ className = 'h-7 w-7' }: { className?: string }) {
    return (
        <svg viewBox="0 0 32 32" className={className} aria-hidden>
            <path d="M16 3 L28 26 H4 Z" fill="#0E1510" />
            <rect x="7" y="17" width="18" height="4" rx="1" fill="#C6F432" />
        </svg>
    );
}

function Field({ label, aside, ...input }: React.InputHTMLAttributes<HTMLInputElement> & { label: string; aside?: React.ReactNode }) {
    return (
        <label className="flex flex-col gap-[7px]">
            <span className="flex justify-between text-[13px] font-semibold text-ink">{label}{aside}</span>
            <input {...input}
                className="h-[46px] rounded-xl border border-[#D5DBD0] bg-paper px-3.5 text-[15px] text-ink outline-none transition focus:border-ink focus:ring-0 placeholder:text-muted" />
        </label>
    );
}

export function LoginPage() {
    const navigate = useNavigate();
    const login = useAuthStore((s) => s.login);
    const [methods, setMethods] = useState<Methods | null>(null);
    const [identity, setIdentity] = useState('');
    const [username, setUsername] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [show, setShow] = useState(false);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        api.get<Methods>('/auth/methods').then((r) => setMethods(r.data))
            .catch(() => setMethods({ password: true, first_run: false, signup_open: false }));
    }, []);

    const creatingAdmin = !!methods?.first_run;

    async function finish(accessToken: string) {
        useAuthStore.setState({ token: accessToken });
        const me = await api.get('/auth/me').then((r) => r.data).catch(() => null);
        login(accessToken, { id: me?.user_id ?? '', username: me?.username ?? identity, email: me?.email ?? email });
        navigate(creatingAdmin ? '/setup' : '/');
    }

    async function submit(e: React.FormEvent) {
        e.preventDefault();
        setBusy(true);
        try {
            if (creatingAdmin) {
                const t = await authService.register({ username, email, password });
                toast.success('Admin account created');
                await finish(t.access_token);
            } else {
                const t = await authService.login({ username: identity, password });
                await finish(t.access_token);
            }
        } catch (err) {
            const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
            toast.error(detail || 'Could not sign in');
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className="flex min-h-screen bg-paper text-ink">
            <div className="flex w-full flex-col px-6 py-10 sm:px-14 lg:w-[600px] lg:shrink-0 lg:px-[88px]">
                <div className="flex items-center gap-2.5">
                    <AssayMark />
                    <span className="font-display text-[23px] font-extrabold tracking-[-0.03em]">assay</span>
                </div>

                <div className="flex flex-1 flex-col justify-center py-10">
                    <form onSubmit={submit} className="flex w-full max-w-[424px] flex-col gap-[22px]">
                        <div className="flex flex-col gap-2">
                            <h1 className="font-display text-[40px] font-extrabold leading-[42px] tracking-[-0.03em]">
                                {creatingAdmin ? 'Set up Assay' : 'Sign in'}
                            </h1>
                            <p className="text-[15px] text-body">
                                {creatingAdmin
                                    ? 'This is a new install. The account you create now is the admin.'
                                    : 'to your Assay workspace'}
                            </p>
                        </div>

                        {creatingAdmin ? (
                            <>
                                <Field label="Name" value={username} onChange={(e) => setUsername(e.target.value)}
                                    placeholder="priya" autoComplete="username" required minLength={3} />
                                <Field label="Work email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                                    placeholder="you@company.com" autoComplete="email" required />
                            </>
                        ) : (
                            <Field label="Email or username" value={identity} onChange={(e) => setIdentity(e.target.value)}
                                placeholder="you@company.com" autoComplete="username" required autoFocus />
                        )}

                        <Field label="Password" type={show ? 'text' : 'password'} value={password}
                            onChange={(e) => setPassword(e.target.value)} required minLength={creatingAdmin ? 8 : 1}
                            autoComplete={creatingAdmin ? 'new-password' : 'current-password'}
                            aside={<button type="button" onClick={() => setShow((v) => !v)}
                                className="text-[13px] font-medium text-assay">{show ? 'Hide' : 'Show'}</button>} />

                        <button type="submit" disabled={busy || !methods}
                            className="flex h-12 items-center justify-center gap-2 rounded-xl bg-ink text-[15px] font-semibold text-white transition hover:bg-[#1A241D] disabled:opacity-60">
                            {busy ? 'One moment…' : creatingAdmin ? 'Create admin account' : 'Sign in'}
                            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="#C6F432" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
                        </button>

                        {!creatingAdmin && (
                            <p className="text-[13px] text-body">
                                New here? <span className="font-semibold text-assay">
                                    {methods?.signup_open ? 'Ask for an account, or create one below' : 'Ask your admin for an invite'}</span>
                            </p>
                        )}
                    </form>
                </div>

                <p className="flex items-center gap-2 text-xs text-muted">
                    <Icon name="verify" className="h-3.5 w-3.5" />
                    Self-hosted. Your documents never leave this workspace.
                </p>
            </div>

            <div className="hidden flex-1 p-4 lg:flex">
                <div className="relative flex flex-1 flex-col justify-end overflow-hidden rounded-3xl bg-ink p-11">
                    <img src="/brand/art/signin.webp" alt="" className="absolute inset-0 h-full w-full object-cover" />
                    <div className="relative flex max-w-[520px] flex-col gap-3.5">
                        <p className="font-display text-[44px] font-extrabold leading-[46px] tracking-[-0.03em] text-white">
                            Every answer, tested against the page it came from.
                        </p>
                        <div className="flex flex-wrap gap-2 text-[13px] text-[#D6DDD7]">
                            {['Claim-level citations', 'Any model', 'Self-hosted'].map((t) => (
                                <span key={t} className="rounded-full border border-[#2A352D] bg-ink/70 px-[11px] py-1.5">{t}</span>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
