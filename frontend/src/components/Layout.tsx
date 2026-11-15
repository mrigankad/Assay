import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import clsx from 'clsx';
import { useAuthStore } from '@/stores/authStore';
import { healthService } from '@/services';
import { Icon } from '@/components/Icon';

function AssayMark({ className = 'h-[26px] w-[26px]' }: { className?: string }) {
    return (
        <svg viewBox="0 0 32 32" className={className} aria-hidden>
            <path d="M16 3 L28 26 H4 Z" fill="#0E1510" />
            <rect x="7" y="17" width="18" height="4" rx="1" fill="#C6F432" />
        </svg>
    );
}

const NAV = [
    { to: '/', icon: 'ask', label: 'Ask', end: true },
    { to: '/documents', icon: 'document', label: 'Documents' },
    { to: '/matrix', icon: 'table', label: 'Matrix' },
    { to: '/evals', icon: 'evals', label: 'Evals' },
    { to: '/models', icon: 'models', label: 'Models' },
    { to: '/audit', icon: 'audit', label: 'Audit log' },
    { to: '/settings', icon: 'settings', label: 'Settings' },
];

export function Layout() {
    const { isAuthenticated, user, logout } = useAuthStore();
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);
    const [health, setHealth] = useState<'healthy' | 'unhealthy' | 'loading'>('loading');

    useEffect(() => {
        healthService.check().then(() => setHealth('healthy')).catch(() => setHealth('unhealthy'));
    }, []);

    return (
        <div className="flex h-screen bg-paper text-ink">
            {open && <div className="fixed inset-0 z-40 bg-ink/30 lg:hidden" onClick={() => setOpen(false)} />}

            <aside className={clsx(
                'fixed inset-y-0 left-0 z-50 flex w-[248px] flex-col gap-[22px] border-r border-rule bg-bench px-3.5 py-5 transition-transform duration-300 lg:static',
                open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
            )}>
                <div className="flex items-center gap-2.5 px-1.5">
                    <AssayMark />
                    <span className="font-display text-[22px] font-extrabold tracking-[-0.03em]">assay</span>
                </div>

                <button onClick={() => { navigate('/'); setOpen(false); }}
                    className="flex h-[38px] items-center gap-2 rounded-[10px] bg-ink px-3 text-sm font-medium text-white">
                    <Icon name="plus" className="h-4 w-4 text-lime" strokeWidth={2} />
                    <span className="flex-1 text-left">New question</span>
                </button>

                <nav className="flex flex-col gap-0.5">
                    {NAV.map((n) => (
                        <NavLink key={n.to} to={n.to} end={n.end} onClick={() => setOpen(false)}
                            className={({ isActive }) => clsx(
                                'flex h-[34px] items-center gap-2.5 rounded-lg px-2.5 text-sm transition-colors',
                                isActive ? 'border border-rule bg-paper font-semibold text-ink' : 'text-dark-200 hover:bg-paper/70',
                            )}>
                            {({ isActive }) => (<>
                                <Icon name={n.icon} className={clsx('h-[18px] w-[18px]', isActive ? 'text-assay' : 'text-body')} />
                                {n.label}
                            </>)}
                        </NavLink>
                    ))}
                </nav>

                <div className="flex-1" />

                <div className="flex items-center gap-2 px-2.5 text-xs text-body">
                    <span className={clsx('h-2 w-2 rounded-full',
                        health === 'healthy' && 'bg-assay', health === 'unhealthy' && 'bg-dropped', health === 'loading' && 'bg-conflict')} />
                    {health === 'healthy' ? 'Engine online' : health === 'unhealthy' ? 'Engine offline' : 'Checking…'}
                </div>

                {isAuthenticated && user && (
                    <div className="flex items-center gap-2.5 rounded-xl border border-rule bg-paper p-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink text-sm font-bold text-lime">
                            {user.username.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-[13px] font-semibold">{user.username}</p>
                            <p className="truncate text-xs text-body">{user.email}</p>
                        </div>
                        <button onClick={() => { logout(); navigate('/login'); }} title="Sign out" className="p-1 text-body hover:text-dropped">
                            <Icon name="logout" className="h-[18px] w-[18px]" />
                        </button>
                    </div>
                )}
            </aside>

            <main className="flex min-w-0 flex-1 flex-col">
                <header className="flex items-center justify-between border-b border-rule px-4 py-3 lg:hidden">
                    <button onClick={() => setOpen(true)} className="p-1.5 text-ink" aria-label="Open menu">
                        <Icon name="menu" className="h-6 w-6" />
                    </button>
                    <span className="flex items-center gap-2 font-display text-lg font-extrabold"><AssayMark className="h-5 w-5" />assay</span>
                    <span className="w-9" />
                </header>
                <div className="flex-1 overflow-hidden"><Outlet /></div>
            </main>
        </div>
    );
}
