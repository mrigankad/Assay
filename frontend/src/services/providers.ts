import api from './api';

export interface DetectedProvider {
    id: string;
    name: string;
    kind: 'hyperscaler' | 'lab' | 'inference' | 'aggregator' | 'local' | 'cli';
    caps: string[];
    via: string;
    api_base: string | null;
    models: string[];
    enabled: boolean;
    icon: string | null;
    needs: string | null;
    risk: string | null;
}

export interface CatalogProvider {
    id: string;
    name: string;
    kind: DetectedProvider['kind'];
    prefix: string | null;
    caps: string[];
    env: string[][];
    files: string[];
    port: number | null;
    needs: string | null;
    risk: string | null;
}

export interface RoleAssignment {
    model: string | null;
    api_base: string | null;
    error: string | null;
}

export const ROLE_ORDER = ['planner', 'search', 'expert', 'verifier', 'browser', 'vision', 'synthesis', 'embed', 'rerank'] as const;

export const providerService = {
    async detected(refresh = false): Promise<DetectedProvider[]> {
        const r = await api.get('/providers', { params: { refresh } });
        return r.data.providers;
    },
    async catalog(): Promise<CatalogProvider[]> {
        const r = await api.get('/providers/catalog');
        return r.data.providers;
    },
    async roles(): Promise<Record<string, RoleAssignment>> {
        const r = await api.get('/providers/roles');
        return r.data;
    },
    async test(role: string, model?: string) {
        const r = await api.post('/providers/test', { role, model });
        return r.data as { ok: boolean; model?: string; reply?: string; dimension?: number; latency_ms: number };
    },
};

/** Logo for a provider id; every catalogue id has a file in /brand/providers. */
export const providerLogo = (id: string) => `/brand/providers/${id}.svg`;

/** "anthropic/claude-sonnet-4-5" -> provider id used for the logo. */
export function providerIdFromModel(model: string | null | undefined): string | null {
    if (!model) return null;
    const prefix = model.split('/')[0];
    const map: Record<string, string> = {
        ollama_chat: 'ollama', hosted_vllm: 'vllm', cohere_chat: 'cohere', ai21_chat: 'ai21',
        sagemaker_chat: 'sagemaker', claude_code: 'claude_code', codex_cli: 'codex_cli', gemini_cli: 'gemini_cli',
    };
    return map[prefix] ?? prefix;
}
