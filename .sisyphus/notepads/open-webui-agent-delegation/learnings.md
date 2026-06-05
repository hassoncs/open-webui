## 2026-05-18 - Open WebUI agent/tool delegation research <!-- oc:id=sec_010100 -->

- Open WebUI does support external execution surfaces, but they split into two different lanes:
  - external model or agent backends over an OpenAI-compatible API
  - external tool backends over OpenAPI or MCP

- External agent backend, model lane:
  - Official docs say Open WebUI can "connect an agent" like Hermes Agent or OpenClaw by pointing Open WebUI at the agent's OpenAI-compatible API gateway.
  - The practical config knob is `OPENAI_API_BASE_URL` or `OPENAI_API_BASE_URLS` plus matching `OPENAI_API_KEY` or `OPENAI_API_KEYS` in `backend/open_webui/config.py`.
  - Code loads these at `backend/open_webui/config.py:1141` through `backend/open_webui/config.py:1166`.
  - Runtime model routing uses those base URLs in `backend/open_webui/routers/openai.py:618`, `backend/open_webui/routers/openai.py:1164`, and `backend/open_webui/routers/openai.py:1543`.
  - Conclusion: if an OpenCode-compatible server exposes an OpenAI-compatible `/v1` API, Open WebUI can use it as the primary model or agent backend. This routes chat completion requests to that server, not just tool calls.

- External tool backend, tool lane:
  - Open WebUI has first-class tool server configuration via `TOOL_SERVER_CONNECTIONS` in `backend/open_webui/config.py:1195` through `backend/open_webui/config.py:1208`.
  - Admin CRUD and verification for tool servers live in `backend/open_webui/routers/configs.py:154` through `backend/open_webui/routers/configs.py:223` and `backend/open_webui/routers/configs.py:369` through `backend/open_webui/routers/configs.py:490`.
  - OpenAPI tool servers are fetched and normalized in `backend/open_webui/utils/tools.py:1234` through `backend/open_webui/utils/tools.py:1330`, then executed over HTTP in `backend/open_webui/utils/tools.py:1333` through `backend/open_webui/utils/tools.py:1485`.
  - MCP tool servers are registered as `type: "mcp"`, connected through `backend/open_webui/utils/mcp/client.py`, listed in `backend/open_webui/routers/tools.py:116` through `backend/open_webui/routers/tools.py:156`, and invoked in `backend/open_webui/utils/middleware.py:2654` through `backend/open_webui/utils/middleware.py:2760`.

- MCP status:
  - Official docs say Open WebUI supports native MCP, but only for HTTP transport. Docs say stdio or SSE MCP should be bridged through `mcpo`.
  - Code matches that. `backend/open_webui/utils/mcp/client.py:60` uses `streamablehttp_client(...)`, so the built-in MCP client is HTTP streamable transport, not raw stdio.
  - The UI also warns MCP is experimental in `src/lib/components/AddToolServerModal.svelte:931` through `src/lib/components/AddToolServerModal.svelte:940`.

- Direct tool servers, browser-driven lane:
  - User-selected direct tool servers are attached in chat metadata from `src/lib/components/chat/Chat.svelte:2418` through `src/lib/components/chat/Chat.svelte:2427`.
  - Permission gating for this feature is `direct_tool_servers`, surfaced in `backend/open_webui/config.py:1536` through `backend/open_webui/config.py:1631`, `src/lib/components/admin/Users/Groups/Permissions.svelte:855` through `src/lib/components/admin/Users/Groups/Permissions.svelte:865`, and `src/lib/components/chat/MessageInput.svelte:1944` through `src/lib/components/chat/MessageInput.svelte:1947`.
  - In middleware, direct tools are not executed by the backend tool adapters. They are passed to `event_caller` with `type: "execute:tool"` in `backend/open_webui/utils/middleware.py:1369` through `backend/open_webui/utils/middleware.py:1384` and again at `backend/open_webui/utils/middleware.py:4578` through `backend/open_webui/utils/middleware.py:4590`.
  - That means Open WebUI supports client-side delegated tool execution for direct tool servers, separate from global backend-managed tool servers.

- Limits and architecture notes:
  - There is no repo evidence of a dedicated "OpenCode" adapter, no `opencode` integration path, and no generic server-side "delegate this tool call to an arbitrary external agent runtime" config apart from:
    - using an OpenAI-compatible agent as the model backend
    - using OpenAPI tool servers
    - using MCP tool servers
    - using Pipelines as an external worker framework
  - `TASK_MODEL_EXTERNAL` exists at `backend/open_webui/config.py:1854` through `backend/open_webui/config.py:1857`, but it is task-model selection metadata, not a general agent delegation router.

- Best fit for an OpenCode-compatible self-hosted server:
  - If it speaks OpenAI-compatible chat completions, use the OpenAI backend path.
  - If it exposes callable tools over HTTP with OpenAPI, use `TOOL_SERVER_CONNECTIONS` as `type: "openapi"`.
  - If it exposes MCP over streamable HTTP, use `TOOL_SERVER_CONNECTIONS` as `type: "mcp"`.
  - If it is stdio-only MCP, front it with `mcpo`.
  - If it is none of the above, the built-in escape hatch is likely a custom Pipeline worker or a native Python Tool/Function, not a stock config toggle.

- Official doc evidence used:
  - Context7 `Open WebUI` docs: "Connect an Agent" says Hermes Agent and OpenClaw work by exposing an OpenAI-compatible API gateway.
  - Context7 docs: Tools page says Open WebUI supports Native HTTP MCP, MCPO proxy for stdio MCP, OpenAPI servers, Workspace Tools, and Pipelines.
  - Context7 docs: Extensibility page says external HTTP integrations are supported for OpenAPI and MCP, while Pipelines run as a separate worker.

## 2026-05-18 - OpenCode bridge spike notes <!-- oc:id=sec_010101 -->

- Local OpenCode server reality:
  - Process is running as `opencode-live serve --hostname=127.0.0.1 --port=4096`.
  - Hitting `http://127.0.0.1:4096/` returns the OpenCode web UI HTML shell, not a JSON API index.
  - Hitting likely OpenAI-style paths like `/v1/models`, `/v1/chat/completions`, `/api/health`, and `/openapi.json` also returns the UI shell, so there is no repo-local proof that the server currently exposes a stock OpenAI-compatible HTTP surface.

- Stable OpenCode server/session API does exist at the SDK layer:
  - `opencode-sdk-integration` guidance documents server detection via `GET /health`.
  - It also documents session-native operations: session create/get/messages, async prompt submission, and SSE event subscription scoped by directory.
  - The important contract is session/event oriented, not chat-completions oriented.

- Practical bridgeability judgment:
  - A thin adapter is feasible for a spike if it maps:
    - OpenWebUI send message -> OpenCode `promptAsync`
    - OpenWebUI thread -> OpenCode session
    - OpenWebUI streaming response -> OpenCode SSE event stream
    - OpenWebUI model/agent choice -> OpenCode agent selection
  - This is not a clean one-to-one semantic match.

- Main abstraction mismatch:
  - OpenWebUI's default truth model is request/response chat with model backends and optional tool servers.
  - OpenCode's truth model is session + directory scope + typed runtime events + agent execution.
  - A proxy can preserve enough behavior for a demo, but it compresses runtime events and session semantics into a chat-completions illusion.

- Company-architecture read:
  - Good spike: lightweight OpenAI-compatible adapter in front of OpenCode to test whether OpenWebUI-like frontend chrome is useful.
  - Bad long-term base: treating OpenWebUI's backend contract as the constitutional interface for an OpenCode-native product.
  - Better long-term base: use OpenCode as source of truth and put a thin custom frontend or existing AI chat UI library directly on native session/event APIs.

- Minimum native frontend contract if we move away from OpenWebUI:
  - server capabilities/health
  - session lifecycle
  - typed message/history fetch
  - async prompt execution
  - typed SSE or websocket events
  - explicit agent catalog/validation
  - optional cancel/retry/attachments/session metadata controls

- Working recommendation right now:
  - Do not fork OpenWebUI first.
  - If we want a fast proof-of-concept, write a tiny adapter server and treat it as disposable.
  - For the company product, lean toward the existing AI chat UI library plus an OpenCode-native frontend contract.
