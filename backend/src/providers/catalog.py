"""
Provider catalogue.

One entry per model provider Assay can talk to. Detection, routing, the
/providers API and the UI all read from this list, so adding a provider is
one new entry here.

Fields
------
id          stable key, also used in config ("bedrock", "ollama", ...)
name        display name
kind        hyperscaler | lab | inference | aggregator | local | cli
prefix      LiteLLM model prefix, or None for custom adapters (CLI backends)
env         groups of env vars; the provider is "configured" when every var
            in ANY one group is set. e.g. [["AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT"]]
files       credential files that also count as configured (~ expanded)
base_url    default API base (informational, LiteLLM knows most of these)
port        default local port for local runtimes (probed on 127.0.0.1)
probe       path to GET when probing a local port, used to fingerprint it
caps        subset of {"chat", "embed", "rerank", "vision"}
icon        simple-icons slug, or None (UI falls back to a monogram)
needs       extra setting the user must give (e.g. Azure deployment name)
risk        short warning shown before enabling (CLI logins)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    kind: str
    prefix: Optional[str]
    caps: frozenset[str]
    env: tuple[tuple[str, ...], ...] = ()
    files: tuple[str, ...] = ()
    base_url: Optional[str] = None
    port: Optional[int] = None
    probe: Optional[str] = None
    icon: Optional[str] = None
    needs: Optional[str] = None
    risk: Optional[str] = None
    default_models: dict[str, str] = field(default_factory=dict)


def _p(id, name, kind, prefix, caps, **kw) -> ProviderSpec:
    env = tuple(tuple(g) if isinstance(g, (list, tuple)) else (g,) for g in kw.pop("env", ()))
    files = tuple(kw.pop("files", ()))
    return ProviderSpec(id, name, kind, prefix, frozenset(caps.split()), env=env, files=files, **kw)


C, CE, CV, CEV, CER, CERV, ER = (
    "chat", "chat embed", "chat vision", "chat embed vision",
    "chat embed rerank", "chat embed rerank vision", "embed rerank",
)

CLI_RISK = (
    "Runs the vendor's official CLI with your own login. Personal use only: "
    "subscription logins are not for shared servers or bulk indexing. Check "
    "the vendor's current terms first."
)

PROVIDERS: list[ProviderSpec] = [
    # ---------------------------------------------------------------- clouds
    _p("azure", "Azure OpenAI / AI Foundry", "hyperscaler", "azure", CERV,
       env=[["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"], ["AZURE_API_KEY", "AZURE_API_BASE"],
            ["AZURE_OPENAI_ENDPOINT", "AZURE_CLIENT_ID", "AZURE_TENANT_ID"]],
       icon="microsoftazure", needs="deployment name (Azure uses deployment names, not model names)"),
    _p("azure_ai", "Azure AI Foundry models (non-OpenAI)", "hyperscaler", "azure_ai", CERV,
       env=[["AZURE_AI_API_KEY", "AZURE_AI_API_BASE"]], icon="microsoftazure"),
    _p("bedrock", "AWS Bedrock", "hyperscaler", "bedrock", CERV,
       env=[["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"], ["AWS_PROFILE"], ["AWS_BEARER_TOKEN_BEDROCK"],
            ["AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_ARN"], ["AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"]],
       files=["~/.aws/credentials", "~/.aws/config"], icon="amazonwebservices",
       default_models={"chat": "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                       "embed": "bedrock/amazon.titan-embed-text-v2:0",
                       "rerank": "bedrock/cohere.rerank-v3-5:0"}),
    _p("sagemaker", "AWS SageMaker endpoints", "hyperscaler", "sagemaker_chat", CE,
       env=[["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "SAGEMAKER_ENDPOINT"]], icon="amazonwebservices",
       needs="endpoint name"),
    _p("vertex_ai", "Google Vertex AI", "hyperscaler", "vertex_ai", CERV,
       env=[["GOOGLE_APPLICATION_CREDENTIALS"], ["VERTEXAI_PROJECT"], ["GOOGLE_CLOUD_PROJECT"]],
       files=["~/.config/gcloud/application_default_credentials.json",
              "%APPDATA%/gcloud/application_default_credentials.json"],
       icon="googlecloud",
       default_models={"chat": "vertex_ai/gemini-2.5-pro", "embed": "vertex_ai/text-embedding-005"}),
    _p("oci", "Oracle OCI Generative AI", "hyperscaler", "oci", CERV,
       env=[["OCI_COMPARTMENT_ID"]], files=["~/.oci/config"], icon="oracle"),
    _p("watsonx", "IBM watsonx.ai", "hyperscaler", "watsonx", CER,
       env=[["WATSONX_APIKEY", "WATSONX_URL"], ["WATSONX_TOKEN", "WATSONX_URL"]], icon="ibm",
       needs="WATSONX_PROJECT_ID"),
    _p("dashscope", "Alibaba Model Studio (Qwen)", "hyperscaler", "dashscope", CERV,
       env=["DASHSCOPE_API_KEY"], icon="alibabacloud",
       default_models={"chat": "dashscope/qwen-max", "embed": "dashscope/text-embedding-v3"}),
    _p("volcengine", "Volcengine Ark (Doubao)", "hyperscaler", "volcengine", CEV, env=["ARK_API_KEY"]),
    _p("cloudflare", "Cloudflare Workers AI", "inference", "cloudflare", CEV,
       env=[["CLOUDFLARE_API_KEY", "CLOUDFLARE_ACCOUNT_ID"]], icon="cloudflare"),
    _p("databricks", "Databricks Model Serving", "hyperscaler", "databricks", CE,
       env=[["DATABRICKS_HOST", "DATABRICKS_TOKEN"]], files=["~/.databrickscfg"], icon="databricks"),
    _p("snowflake", "Snowflake Cortex", "hyperscaler", "snowflake", CE,
       env=[["SNOWFLAKE_ACCOUNT_ID", "SNOWFLAKE_JWT"], ["SNOWFLAKE_ACCOUNT_ID", "SNOWFLAKE_PAT"]],
       icon="snowflake"),

    # ------------------------------------------------------------ model labs
    _p("openai", "OpenAI", "lab", "openai", CEV, env=["OPENAI_API_KEY"], icon="openai",
       default_models={"chat": "openai/gpt-5", "embed": "openai/text-embedding-3-large"}),
    _p("anthropic", "Anthropic API", "lab", "anthropic", CV, env=["ANTHROPIC_API_KEY"], icon="anthropic",
       default_models={"chat": "anthropic/claude-sonnet-4-5"}),
    _p("gemini", "Google Gemini API", "lab", "gemini", CEV, env=["GEMINI_API_KEY", "GOOGLE_API_KEY"],
       icon="googlegemini",
       default_models={"chat": "gemini/gemini-2.5-pro", "embed": "gemini/gemini-embedding-001"}),
    _p("mistral", "Mistral AI", "lab", "mistral", CEV, env=["MISTRAL_API_KEY"], icon="mistralai",
       default_models={"chat": "mistral/mistral-large-latest", "embed": "mistral/mistral-embed"}),
    _p("codestral", "Mistral Codestral", "lab", "codestral", C, env=["CODESTRAL_API_KEY"], icon="mistralai"),
    _p("cohere", "Cohere", "lab", "cohere_chat", CER, env=["COHERE_API_KEY", "CO_API_KEY"], icon="cohere",
       default_models={"chat": "cohere_chat/command-a-03-2025", "embed": "cohere/embed-v4.0",
                       "rerank": "cohere/rerank-v3.5"}),
    _p("xai", "xAI Grok", "lab", "xai", CV, env=["XAI_API_KEY"], icon="x"),
    _p("deepseek", "DeepSeek", "lab", "deepseek", C, env=["DEEPSEEK_API_KEY"],
       default_models={"chat": "deepseek/deepseek-chat"}),
    _p("moonshot", "Moonshot Kimi", "lab", "moonshot", CV, env=["MOONSHOT_API_KEY"]),
    _p("zai", "Z.ai / Zhipu GLM", "lab", "zai", CEV, env=["ZAI_API_KEY", "ZHIPUAI_API_KEY"]),
    _p("minimax", "MiniMax", "lab", "minimax", C, env=["MINIMAX_API_KEY"]),
    _p("perplexity", "Perplexity", "lab", "perplexity", C, env=["PERPLEXITYAI_API_KEY", "PERPLEXITY_API_KEY"],
       icon="perplexity"),
    _p("ai21", "AI21 Labs", "lab", "ai21_chat", C, env=["AI21_API_KEY"]),
    _p("meta_llama", "Meta Llama API", "lab", "meta_llama", CV, env=["LLAMA_API_KEY"], icon="meta"),

    # ------------------------------------------------------- inference APIs
    _p("groq", "Groq", "inference", "groq", CV, env=["GROQ_API_KEY"]),
    _p("cerebras", "Cerebras", "inference", "cerebras", C, env=["CEREBRAS_API_KEY"]),
    _p("sambanova", "SambaNova", "inference", "sambanova", CEV, env=["SAMBANOVA_API_KEY"]),
    _p("together_ai", "Together AI", "inference", "together_ai", CERV,
       env=["TOGETHERAI_API_KEY", "TOGETHER_API_KEY"]),
    _p("fireworks_ai", "Fireworks AI", "inference", "fireworks_ai", CEV, env=["FIREWORKS_API_KEY"]),
    _p("deepinfra", "DeepInfra", "inference", "deepinfra", CERV, env=["DEEPINFRA_API_KEY"]),
    _p("replicate", "Replicate", "inference", "replicate", CV,
       env=["REPLICATE_API_KEY", "REPLICATE_API_TOKEN"], icon="replicate"),
    _p("huggingface", "Hugging Face Inference", "inference", "huggingface", CEV,
       env=["HF_TOKEN", "HUGGINGFACE_API_KEY", "HUGGING_FACE_HUB_TOKEN"],
       files=["~/.cache/huggingface/token"], icon="huggingface"),
    _p("novita", "Novita AI", "inference", "novita", CE, env=["NOVITA_API_KEY"]),
    _p("hyperbolic", "Hyperbolic", "inference", "hyperbolic", CV, env=["HYPERBOLIC_API_KEY"]),
    _p("nebius", "Nebius AI Studio", "inference", "nebius", CEV, env=["NEBIUS_API_KEY"]),
    _p("lambda_ai", "Lambda Inference", "inference", "lambda_ai", C, env=["LAMBDA_API_KEY"]),
    _p("baseten", "Baseten", "inference", "baseten", CE, env=["BASETEN_API_KEY"]),
    _p("featherless_ai", "Featherless", "inference", "featherless_ai", C, env=["FEATHERLESS_API_KEY"]),
    _p("nscale", "Nscale", "inference", "nscale", C, env=["NSCALE_API_KEY"]),
    _p("ovhcloud", "OVHcloud AI Endpoints", "inference", "ovhcloud", CE, env=["OVHCLOUD_API_KEY"],
       icon="ovh"),
    _p("friendliai", "FriendliAI", "inference", "friendliai", C, env=["FRIENDLI_TOKEN"]),
    _p("clarifai", "Clarifai", "inference", "clarifai", CV, env=["CLARIFAI_PAT"]),
    _p("nvidia_nim", "NVIDIA NIM", "inference", "nvidia_nim", CERV,
       env=["NVIDIA_NIM_API_KEY", "NVIDIA_API_KEY"], icon="nvidia",
       default_models={"chat": "nvidia_nim/nvidia/llama-3.3-nemotron-super-49b-v1",
                       "embed": "nvidia_nim/nvidia/llama-3.2-nv-embedqa-1b-v2",
                       "rerank": "nvidia_nim/nvidia/llama-3.2-nv-rerankqa-1b-v2"}),
    _p("jina_ai", "Jina AI", "inference", "jina_ai", ER, env=["JINA_AI_API_KEY", "JINA_API_KEY"],
       default_models={"embed": "jina_ai/jina-embeddings-v3", "rerank": "jina_ai/jina-reranker-v2-base-multilingual"}),
    _p("voyage", "Voyage AI", "inference", "voyage", ER, env=["VOYAGE_API_KEY"],
       default_models={"embed": "voyage/voyage-3.5", "rerank": "voyage/rerank-2.5"}),

    # ------------------------------------------------------------ aggregators
    _p("openrouter", "OpenRouter", "aggregator", "openrouter", CEV, env=["OPENROUTER_API_KEY"],
       icon="openrouter"),
    _p("vercel_ai_gateway", "Vercel AI Gateway", "aggregator", "vercel_ai_gateway", CEV,
       env=["AI_GATEWAY_API_KEY", "VERCEL_OIDC_TOKEN"], icon="vercel"),
    _p("litellm_proxy", "LiteLLM Proxy", "aggregator", "litellm_proxy", CERV,
       env=[["LITELLM_PROXY_API_BASE"]], port=4000, probe="/health/liveliness"),
    _p("github", "GitHub Models", "aggregator", "github", CEV, env=["GITHUB_TOKEN", "GITHUB_API_KEY"],
       icon="github"),

    # --------------------------------------------------------- local runtimes
    _p("ollama", "Ollama (local or -cloud models)", "local", "ollama_chat", CEV, env=[["OLLAMA_API_BASE"], ["OLLAMA_HOST"]],
       port=11434, probe="/api/tags", icon="ollama"),
    _p("ollama_cloud", "Ollama Cloud", "inference", "ollama_chat", CE, env=["OLLAMA_API_KEY"],
       base_url="https://ollama.com", icon="ollama"),
    _p("lm_studio", "LM Studio", "local", "lm_studio", CEV, env=["LM_STUDIO_API_BASE"],
       port=1234, probe="/v1/models"),
    _p("vllm", "vLLM", "local", "hosted_vllm", CERV, env=["HOSTED_VLLM_API_BASE"],
       port=8000, probe="/v1/models"),
    _p("sglang", "SGLang", "local", "openai", CEV, port=30000, probe="/v1/models"),
    _p("llamacpp", "llama.cpp server", "local", "openai", CERV, port=8080, probe="/v1/models"),
    _p("llamafile", "llamafile", "local", "llamafile", C, env=["LLAMAFILE_API_BASE"]),
    _p("localai", "LocalAI", "local", "openai", CERV, port=8080, probe="/readyz"),
    _p("jan", "Jan", "local", "openai", C, port=1337, probe="/v1/models"),
    _p("gpt4all", "GPT4All", "local", "openai", CE, port=4891, probe="/v1/models"),
    _p("koboldcpp", "KoboldCpp", "local", "openai", C, port=5001, probe="/api/v1/model"),
    _p("textgen_webui", "text-generation-webui", "local", "openai", CE, port=5000, probe="/v1/models"),
    _p("xinference", "Xinference", "local", "xinference", CER, env=["XINFERENCE_API_BASE"],
       port=9997, probe="/v1/models"),
    _p("tgi", "Hugging Face TGI / TEI", "local", "huggingface", CE, port=8080, probe="/info",
       icon="huggingface"),
    _p("triton", "NVIDIA Triton", "local", "triton", CE, port=8000, probe="/v2/health/ready", icon="nvidia"),
    _p("infinity", "Infinity (embed + rerank)", "local", "infinity", ER, port=7997, probe="/models"),
    _p("docker_model_runner", "Docker Model Runner", "local", "openai", CE, port=12434,
       probe="/engines/v1/models", icon="docker"),
    _p("mlx", "MLX (mlx-lm server)", "local", "openai", C, port=8080, probe="/v1/models", icon="apple"),

    # ------------------------------------------------------------- CLI logins
    _p("claude_code", "Claude Code (local login)", "cli", None, C, icon="claude", risk=CLI_RISK,
       default_models={"chat": "claude_code/"}),
    _p("codex_cli", "Codex CLI (local login)", "cli", None, C, icon="openai", risk=CLI_RISK,
       default_models={"chat": "codex_cli/"}),
    _p("gemini_cli", "Gemini CLI (local login)", "cli", None, C, icon="googlegemini", risk=CLI_RISK,
       default_models={"chat": "gemini_cli/"}),

    # -------------------------------------------------------------- built in
    _p("builtin", "Built-in ONNX (offline)", "local", None, ER,
       default_models={"embed": "builtin/bge-small-en-v1.5", "rerank": "builtin/ms-marco-MiniLM-L-6-v2"}),
]

BY_ID: dict[str, ProviderSpec] = {p.id: p for p in PROVIDERS}

CLI_BINARIES = {"claude_code": "claude", "codex_cli": "codex", "gemini_cli": "gemini"}
