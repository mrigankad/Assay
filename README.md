<p align="center">
  <img src="docs/readme/hero.png" alt="Assay: answers you can check" width="100%"/>
</p>

Assay is an open-source research engine for long documents. Ask it a hard question about a 400-page filing, a stack of contracts or a tender, and it plans the search, reads the evidence, checks each sentence of its answer against the page it came from, and drops anything it can't support. It runs on your machine or your cloud, with whichever models you already have.

<p align="center"><img src="docs/readme/ui-ask.png" alt="An answer with a verified claim highlighted and the source clause boxed on the PDF page" width="100%"/></p>

## Why it exists

Most document chat tools cite a document. Assay cites the sentence, shows the region of the page, and tells you when two sources disagree. Every answer keeps a trace (plan, sources, model, tokens, cost) you can replay later.

<p align="center"><img src="docs/readme/how.png" alt="Plan, retrieve, browse, write, verify" width="100%"/></p>

## Bring any model

<p align="center"><img src="docs/readme/models.png" alt="Provider logos: OpenAI, Anthropic, Gemini, Azure, Bedrock, Vertex and more" width="100%"/></p>

On start, Assay looks for:

- **API keys** in the environment: OpenAI, Anthropic, Gemini, Mistral, Cohere, Groq, Together, Fireworks, DeepSeek, xAI, OpenRouter and [60 more](docs/PROVIDERS.md).
- **Cloud logins**: AWS (profiles, SSO, roles) for Bedrock and SageMaker, Azure OpenAI and AI Foundry (keys or Entra ID), Google Vertex (ADC), Oracle OCI, IBM watsonx, Alibaba, Databricks, Snowflake, Cloudflare.
- **Local servers**, found by probing their ports: Ollama, LM Studio, vLLM, SGLang, llama.cpp, LocalAI, Jan, GPT4All, KoboldCpp, text-generation-webui, Xinference, TGI/TEI, Triton, Infinity, Docker Model Runner, MLX.
- **Built-in offline embeddings and reranking** (ONNX), so retrieval works with no key at all.
- **Vendor CLIs** (Claude Code, Codex, Gemini CLI) with your own login. These are off until you opt in, and are for personal use only.

Each agent role (planner, search, experts, verifier, browser, vision, writer, embeddings, rerank) can use a different model. Assay picks sensible defaults; override any role with `ASSAY_MODEL_<ROLE>`.

<p align="center"><img src="docs/readme/ui-models.png" alt="Models screen: detected connections and the model used for each role" width="100%"/></p>

## Quick start

You need Python 3.12+, Node 20+ and one model source (an API key, a cloud login, or Ollama running locally).

```bash
git clone https://github.com/mrigankad/assay.git && cd assay
cp .env.example .env            # add a key, or skip this if Ollama / a cloud login is already set up

cd backend
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd .. && make dev-local          # API on http://localhost:8000 (SQLite + embedded Qdrant, no Docker)

cd frontend && npm install && npm run dev        # UI on http://localhost:3000
```

Then open **Models** to see what was found, upload documents under **Documents**, and ask.

Full stack with Postgres, Redis, Qdrant and a worker: `cp .env.example .env && make init`.

## What's inside

| | |
|---|---|
| **Retrieval** | Dense + BM25 sparse vectors fused with Reciprocal Rank Fusion, reranking, a relevance gate that rewrites and retries weak queries, per-document outline chunks for overview questions. |
| **Ingestion** | PDF, DOCX, Markdown, HTML, CSV and text, with heading-aware chunks, tables kept whole and page-level locations. |
| **Agents** | Planner, search, 50 domain personas, verifier and writer. A browser agent (opt-in) reads the web and snapshots every page it cites. |
| **Answers** | One grounded answer from numbered evidence. Citations that point nowhere are removed. Confidence is derived, not asserted. |
| **Access** | Every chunk carries ACL principals. Local JWT auth or Microsoft Entra ID. Connectors sync source permissions (SharePoint, Google Drive, Confluence, S3, web, folders). |
| **Data** | `data.query` answers questions over SQL databases through a read-only, policy-checked gateway. |
| **Interop** | Assay is an MCP server at `/mcp`, and can use any MCP knowledge server (including Azure AI Search / Foundry IQ) as its backend. |
| **Ops** | OpenTelemetry traces, per-answer token and cost accounting, an offline eval harness, Docker Compose. |

## API

- `GET /api/providers` · what was detected · `?refresh=true` to rescan
- `GET /api/providers/roles` · the model each role uses right now
- `POST /api/providers/test` · `{"role": "verifier"}` sends a one-word prompt and reports latency
- `POST /api/chat` · SSE stream of `progress`, `evidence`, `answer_delta`, `done`
- Swagger at `/docs`

## Status

Assay grew out of [Dexter](https://github.com/mrigankad/Dexter-retrival-engine) and the Bodham rebuild of it. Working today: everything in the table above, and the provider layer across all 73 providers (detection is unit-tested; live calls verified through the Claude Code CLI login and Ollama Cloud). In progress: page-region (bounding-box) citations in the UI, the claim-by-claim verifier view, the browser agent, the eval dashboard and model comparison.

## Licence

MIT. Provider logos come from [LobeHub Icons](https://github.com/lobehub/lobe-icons) (MIT) and [simple-icons](https://simpleicons.org) (CC0) and remain trademarks of their owners.
