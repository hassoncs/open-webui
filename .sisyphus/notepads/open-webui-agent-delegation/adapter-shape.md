## Thin adapter shape: OpenWebUI -> OpenCode <!-- oc:id=sec_53a937 -->

### Goal <!-- oc:id=sec_28fe3a -->

Make OpenWebUI believe it is talking to an OpenAI-compatible chat backend while the adapter actually drives native OpenCode sessions and event streams.

This is a spike harness, not the desired long-term product boundary.

### Request mapping <!-- oc:id=sec_87df65 -->

- `POST /v1/chat/completions`
  - Input from OpenWebUI: model, messages, stream, tools/tool_choice maybe, metadata maybe.
  - Adapter responsibilities:
    - resolve or create an OpenCode session for the conversation/thread
    - map selected OpenWebUI `model` to an OpenCode `agent` or agent preset
    - collapse the latest user turn into an OpenCode prompt payload
    - call OpenCode session prompt API (`promptAsync` style)
    - subscribe to the matching session or directory SSE stream
    - convert typed OpenCode events into OpenAI-style streaming deltas or final response JSON

### Required state in adapter <!-- oc:id=sec_809947 -->

- conversation id -> OpenCode session id
- conversation id -> directory/workspace scope
- model alias -> OpenCode agent id
- stream subscribers for in-flight turns
- best-effort replay/cache of last assistant text for non-stream requests

### Event translation <!-- oc:id=sec_7b1916 -->

OpenCode runtime likely emits richer events than OpenAI chat completions. The adapter must decide what survives.

- preserve as assistant text deltas:
  - message text updates
- preserve as synthetic tool-call blocks if possible:
  - tool started/completed
- preserve as side-channel metadata only:
  - session status changes
  - directory-scoped events
  - agent routing info
  - internal validation events

### Places where the adapter stops being thin <!-- oc:id=sec_60e00c -->

- reconstructing thread history into prompts instead of relying on native session truth
- hiding async execution lifecycle behind synchronous request semantics
- faking OpenAI tool call structure from richer OpenCode tool/runtime events
- inventing cancellation/retry semantics OpenWebUI expects but OpenCode names differently
- carrying filesystem/artifact/sidebar concepts through a protocol that only understands chat turns

### Minimal viable spike <!-- oc:id=sec_21d9fc -->

1. hardcode one workspace directory <!-- oc:id=item_59da65 -->
1. hardcode one OpenCode agent mapping <!-- oc:id=item_e5c484 -->
1. support `POST /v1/chat/completions` only <!-- oc:id=item_357741 -->
1. support `stream: true` <!-- oc:id=item_8b305c -->
1. ignore OpenAI tools/function-calling in v1 <!-- oc:id=item_8b8ee2 -->
1. emit plain assistant deltas only <!-- oc:id=item_669d58 -->
1. store session mapping in memory <!-- oc:id=item_edb04d -->

If this already feels awkward, that is signal to skip OpenWebUI as the main UI base.

### Better native UI contract <!-- oc:id=sec_7227bb -->

If we use the existing AI chat UI library directly, the browser/backend contract should expose:

- `GET /health`
- `GET /agents`
- `POST /sessions`
- `GET /sessions/:id`
- `GET /sessions/:id/messages`
- `POST /sessions/:id/prompts`
- `GET /sessions/:id/events` (SSE or websocket)
- `POST /sessions/:id/cancel`
- optional attachments/artifacts endpoints later

### Decision test <!-- oc:id=sec_c0e06c -->

If the adapter can stay under roughly:

- one `POST /v1/chat/completions` endpoint
- one stream translator
- one small session store
- one model->agent mapper

then it is a healthy spike.

If it immediately wants:

- custom history synthesis
- tool-call emulation
- side-panel artifact shadow state
- background job reconciliation
- directory/workspace orchestration logic

then stop and move to the native UI path.
