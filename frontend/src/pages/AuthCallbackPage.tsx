import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '@/services/api';
import { finishSso } from '@/services/sso';
import { useAuthStore } from '@/stores/authStore';

export function AuthCallbackPage() {
    const navigate = useNavigate();
    const login = useAuthStore((s) => s.login);
    const [error, setError] = useState<string | null>(null);
    const ran = useRef(false);

    useEffect(() => {
        if (ran.current) return;            // the code can only be used once (StrictMode runs effects twice)
        ran.current = true;
        (async () => {
            try {
                const token = await finishSso(new URLSearchParams(window.location.search));
                useAuthStore.setState({ token });
                const me = (await api.get('/auth/me')).data;
                login(token, { id: me.user_id, username: me.username, email: me.email });
                navigate('/', { replace: true });
            } catch (e) {
                const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
                setError(detail || (e as Error).message || 'Sign-in failed');
            }
        })();
    }, [login, navigate]);

    return (
        <div className="flex min-h-screen items-center justify-center bg-bench px-6 text-ink">
            <div className="flex max-w-[420px] flex-col items-center gap-4 text-center">
                <svg viewBox="0 0 32 32" className="h-9 w-9"><path d="M16 3 L28 26 H4 Z" fill="#0E1510" /><rect x="7" y="17" width="18" height="4" rx="1" fill="#C6F432" /></svg>
                {error ? (
                    <>
                        <h1 className="font-display text-2xl font-bold">Couldn’t sign you in</h1>
                        <p className="text-sm text-body">{error}</p>
                        <Link to="/login" className="rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white">Back to sign in</Link>
                    </>
                ) : (
                    <p className="text-sm text-body">Signing you in…</p>
                )}
            </div>
        </div>
    );
}
