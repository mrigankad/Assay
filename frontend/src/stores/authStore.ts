import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types';

interface AuthState {
    token: string | null;
    user: User | null;
    isAuthenticated: boolean;

    // Actions
    login: (token: string, user: User) => void;
    logout: () => void;
    updateUser: (user: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            token: null,
            user: null,
            isAuthenticated: false,

            login: (token: string, user: User) => {
                set({
                    token,
                    user,
                    isAuthenticated: true,
                });
            },

            logout: () => {
                // Conversations belong to the signed-in user: never leave them for the next person on this browser.
                try { localStorage.removeItem('rag-chat-history'); } catch { /* storage blocked */ }
                import('@/stores/chatStore').then((m) => m.useChatStore.getState().clearMessages()).catch(() => undefined);
                set({
                    token: null,
                    user: null,
                    isAuthenticated: false,
                });
            },

            updateUser: (userData: Partial<User>) => {
                set((state) => ({
                    user: state.user ? { ...state.user, ...userData } : null,
                }));
            },
        }),
        {
            name: 'rag-auth-storage',
            partialize: (state) => ({
                token: state.token,
                user: state.user,
                isAuthenticated: state.isAuthenticated,
            }),
        }
    )
);
