# Open WebUI Generated File Access <!-- oc:id=sec_ae03e5 -->

## TL;DR <!-- oc:id=sec_b4fe73 -->

> **Summary**: Make assistant-generated sandbox files under `/mnt/uploads/...` behave like first-class artifacts in chat: click opens the correct Files pane, view/download works immediately, and durable backend publication is explicit rather than implied.
> **Deliverables**:
>
> - Pyodide-specific open-by-path routing from chat output into `PyodideFileNav`
> - Sandbox file chip UX replacing raw clickable code/path text
> - Richer Pyodide preview support for common generated file types
> - Explicit publish-to-backend flow for durable Open WebUI file access
>   **Effort**: Medium
>   **Parallel**: YES - 3 waves
>   **Critical Path**: `tid_matcher_contract` → `tid_sandbox_open_routing` → `tid_file_chip_surface` → `tid_preview_parity` → `tid_publish_flow`

## Context <!-- oc:id=sec_7685a5 -->

### Original Request <!-- oc:id=sec_9b54a8 -->

Turn the generated-file UX investigation into a real execution plan so users can click generated files from chat and either view or download them, instead of only getting a copied `/mnt/...` path.

### Interview Summary <!-- oc:id=sec_a20505 -->

- Generated code-interpreter files live in Pyodide `/mnt/uploads`, not Docker host storage or backend Open WebUI file storage.
- Current UX misleads users because the assistant may emit a sandbox path as inline code, and inline code clicks copy text instead of opening a file.
- Existing UI primitives already cover most needs: `PyodideFileNav` for sandbox browsing/downloads and `FilePreview` / `FileItemModal` for rich inline preview.
- The preferred product shape is phased: route/open first, then improve file chips, then preview parity, then optional explicit publish flow.

### Metis Review (gaps addressed) <!-- oc:id=sec_f812d5 -->

- Guardrail added: phase 1 only recognizes exact `/mnt/uploads/...` file paths to avoid hijacking generic inline code behavior.
- Guardrail added: no bind mounts, no silent backend publication, no preview-architecture merge in phase 1.
- Acceptance criteria added for missing-file UX, copy-behavior preservation, Files-tab switching, and per-phase separation.
- Risk acknowledged: sandbox files are browser-global IDBFS, not chat-scoped; this remains out of scope for this plan.

## Work Objectives <!-- oc:id=sec_ee9be2 -->

### Core Objective <!-- oc:id=sec_c53253 -->

Make sandbox-generated files accessible from chat as first-class local artifacts by routing clicks into the existing Pyodide Files pane, then layer on clearer file chips, richer preview support, and an explicit durable publish path.

### Deliverables <!-- oc:id=sec_9a969b -->

- Path-matcher and regression tests that distinguish sandbox file paths from ordinary inline code.
- New Pyodide open-path store and routing through the existing chat controls / Files tab.
- Updated inline path behavior so `/mnt/uploads/...` opens the sandbox file instead of copying it.
- Dedicated sandbox file chip rendering in assistant messages.
- Pyodide preview support for PDFs, audio, video, and other common generated artifacts using existing viewer surfaces where practical.
- Explicit publish-to-backend workflow that creates backend `file` records and exposes durable `/api/v1/files/{id}/content` URLs only on user or flow request.

### Definition of Done (verifiable conditions with commands) <!-- oc:id=sec_03e1d2 -->

- `/mnt/uploads/...` code-span clicks open the chat Files tab and select the correct sandbox file.
- Non-path inline code still copies to clipboard.
- Sandbox file chips render for generated file references and expose open/download actions.
- Supported sandbox file types preview inline without forcing raw path discovery.
- Explicit publish flow creates backend durable files and makes them accessible via existing backend file routes.
- Verification commands complete successfully:
  - `pnpm test -- --runInBand src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens/CodespanToken.test.*`
  - `pnpm test -- --runInBand src/lib/components/chat/PyodideFileNav.test.* src/lib/components/chat/ChatControls.test.*`
  - `pnpm test -- --runInBand src/lib/components/chat/Messages/Markdown/SandboxFileToken.test.*`
  - `pnpm test -- --runInBand src/lib/components/chat/FileNav/FilePreview.test.*`
  - `pnpm exec playwright test tests/generated-file-access.spec.*`

### Must Have <!-- oc:id=sec_e43266 -->

- Exact sandbox-path detection for `/mnt/uploads/...` only in phase 1.
- Distinct routing for sandbox files vs terminal/backend files.
- Click-to-open behavior that uses the existing Files pane and `PyodideFileNav`.
- Clear missing-file handling when sandbox state no longer contains the referenced file.
- Preserve existing copy semantics for ordinary inline code spans.
- Sandbox-file affordance that makes view/download obvious.
- Explicit durable publish step rather than silent persistence.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries) <!-- oc:id=sec_e69aa7 -->

- Must NOT bind-mount `/mnt` or treat it as Docker-host storage.
- Must NOT route sandbox paths through backend `/api/v1/files/{id}/content` unless published.
- Must NOT auto-publish every sandbox file to backend storage.
- Must NOT broaden phase 1 matching to arbitrary `/mnt/...` or generic absolute paths.
- Must NOT merge `FileNav` and `PyodideFileNav` architectures in this workstream.
- Must NOT redesign sandbox persistence scope or per-chat isolation.

## Verification Strategy <!-- oc:id=sec_418df2 -->

> ZERO HUMAN INTERVENTION — all verification is agent-executed.

- Test decision: tests-after with existing frontend/component + Playwright coverage.
- QA policy: Every task includes agent-executed scenarios and evidence artifacts.
- Evidence: `.sisyphus/evidence/task-{task-id}-{slug}.{ext}`

## Execution Strategy <!-- oc:id=sec_6b7027 -->

### Parallel Execution Waves <!-- oc:id=sec_4d7777 -->

> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: contract and routing foundation (`tid_matcher_contract`, `tid_sandbox_open_routing`)

Wave 2: message-surface UX (`tid_codespan_open_behavior`, `tid_file_chip_surface`)

Wave 3: richer access paths (`tid_preview_parity`, `tid_publish_flow`)

### Dependency Matrix (full, all tasks) <!-- oc:id=sec_52cb1d -->

- `tid_matcher_contract` blocks `tid_codespan_open_behavior`, `tid_file_chip_surface`
- `tid_sandbox_open_routing` blocks `tid_codespan_open_behavior`, `tid_file_chip_surface`, `tid_preview_parity`
- `tid_codespan_open_behavior` should land before `tid_file_chip_surface` so raw path clicks are fixed even if chips slip
- `tid_file_chip_surface` should land before `tid_publish_flow` so publish can reuse artifact UI affordances
- `tid_preview_parity` is independent of publish, but both depend on routing being stable

### Agent Dispatch Summary (wave → task count → categories) <!-- oc:id=sec_c05c4d -->

- Wave 1 → 2 tasks → `quick`, `unspecified-low`
- Wave 2 → 2 tasks → `visual-engineering`, `quick`
- Wave 3 → 2 tasks → `unspecified-high`, `deep`

## TODOs <!-- oc:id=sec_148b4b -->

> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] [tid_matcher_contract] Lock sandbox path detection and regression behavior

  **What to do**: Add tests and any minimal shared helper needed to define the phase-1 sandbox-path contract: only exact file paths under `/mnt/uploads/...` qualify for sandbox-file open behavior. Include regression coverage proving that ordinary inline code, shell commands, and arbitrary absolute paths still use copy-to-clipboard semantics.
  **Must NOT do**: Must NOT wire UI routing yet. Must NOT broaden matching beyond `/mnt/uploads/...`. Must NOT change runtime behavior without tests that fail first.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: bounded matcher + regression test slice.
  - Skills: [`test`] — reason: focused component/unit proof first.
  - Omitted: [`playwright`] — reason: phase 1 contract should be locked at component/helper level before browser proof.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `tid_codespan_open_behavior`, `tid_file_chip_surface` | Blocked By: none

  **References**:
  - Pattern: `src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens/CodespanToken.svelte:15` — current copy-on-click behavior for inline code spans.
  - Pattern: `src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens.svelte:104` — codespans are routed through `CodespanToken`.
  - Pattern: `src/lib/workers/pyodide.worker.ts:50` — sandbox upload directory root is `/mnt/uploads`.
  - Pattern: `src/lib/workers/pyodide.worker.ts:52` — `/mnt` is IDBFS, confirming local sandbox scope.

  **Acceptance Criteria**:
  - [ ] A matcher/helper or equivalent component logic recognizes `/mnt/uploads/report.md` as sandbox-openable.
  - [ ] `/mnt/report.md`, `/tmp/report.md`, `pip install foo`, and arbitrary inline code remain copyable, not openable.
  - [ ] Paths with spaces and nested directories under `/mnt/uploads/` are covered by tests.
  - [ ] A missing or malformed sandbox path is treated as ordinary text/copy behavior unless explicitly valid.

  **QA Scenarios**:

  ```
  Scenario: Sandbox path matcher accepts valid generated file paths
    Tool: Bash
    Steps: Run `pnpm test -- --runInBand src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens/CodespanToken.test.*`
    Expected: Tests show `/mnt/uploads/...` opens-file behavior and non-matching code paths stay copy-only.
    Evidence: .sisyphus/evidence/task-tid_matcher_contract-tests.txt

  Scenario: Non-path inline code remains copyable
    Tool: Bash
    Steps: Run the same test target with explicit regression cases for ``pip install foo`` and `/tmp/foo.txt`.
    Expected: Regression assertions pass with no sandbox-open side effects.
    Evidence: .sisyphus/evidence/task-tid_matcher_contract-regression.txt
  ```

  **Commit**: YES | Message: `test(chat): lock sandbox path detection behavior` | Files: `src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens/*`, test files under the matching chat markdown test area

- [x] [tid_sandbox_open_routing] Add Pyodide-specific open-by-path routing into the Files pane

  **What to do**: Introduce a dedicated store for sandbox-file open requests, extend the shared display-file routing helper to dispatch `/mnt/uploads/...` into that store, teach `ChatControls` to switch to the Files tab for sandbox file requests, and teach `PyodideFileNav` to subscribe to the new store, load the containing directory, and open the target file.
  **Must NOT do**: Must NOT reuse terminal-only `showFileNavPath` for sandbox files. Must NOT route sandbox paths into backend or terminal APIs. Must NOT add preview-parity work here.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` — Reason: cross-component store/routing slice with low algorithmic complexity.
  - Skills: [`react-best-practices`] — reason: state/event wiring discipline for frontend surfaces.
  - Omitted: [`visual-engineering`] — reason: this slice is behavioral infrastructure, not visual polish.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: `tid_codespan_open_behavior`, `tid_file_chip_surface`, `tid_preview_parity` | Blocked By: none

  **References**:
  - Pattern: `src/lib/stores/index.ts:106` — existing `showFileNavPath` / `showFileNavDir` stores.
  - Pattern: `src/lib/utils/index.ts:1993` — current `displayFileHandler` behavior.
  - Pattern: `src/lib/components/chat/FileNav.svelte:786` — terminal file open-by-path subscription model.
  - Pattern: `src/lib/components/chat/ChatControls.svelte:96` — current Files-tab auto-switch on file-nav path changes.
  - Pattern: `src/lib/components/chat/PyodideFileNav.svelte:24` — current path state anchored at `/mnt/uploads`.
  - Pattern: `src/lib/components/chat/PyodideFileNav.svelte:333` — existing refresh behavior on `pyodide:files` event.

  **Acceptance Criteria**:
  - [ ] A new sandbox-specific open-path store exists and is used for `/mnt/uploads/...` routing.
  - [ ] Triggering that store opens chat controls and switches to the Files tab when code interpreter is enabled.
  - [ ] `PyodideFileNav` loads the containing directory and opens the targeted file by name.
  - [ ] If the file is missing, the pane still opens and shows a clear not-found state or toast instead of silently failing.
  - [ ] Terminal file routing remains unchanged for non-sandbox paths.

  **QA Scenarios**:

  ```
  Scenario: Sandbox open-path store opens the right file in PyodideFileNav
    Tool: Bash
    Steps: Run `pnpm test -- --runInBand src/lib/components/chat/PyodideFileNav.test.* src/lib/components/chat/ChatControls.test.*`
    Expected: Tests prove Files tab activation and open-by-path behavior for `/mnt/uploads/foo.md`.
    Evidence: .sisyphus/evidence/task-tid_sandbox_open_routing-tests.txt

  Scenario: Missing sandbox file fails clearly
    Tool: Bash
    Steps: Include a test path such as `/mnt/uploads/missing.md` in the same suite.
    Expected: UI state reports not-found behavior without crashing or switching to terminal-backed file nav.
    Evidence: .sisyphus/evidence/task-tid_sandbox_open_routing-missing.txt
  ```

  **Commit**: YES | Message: `feat(chat): route sandbox file paths into pyodide files pane` | Files: `src/lib/stores/index.ts`, `src/lib/utils/index.ts`, `src/lib/components/chat/Chat.svelte`, `src/lib/components/chat/ChatControls.svelte`, `src/lib/components/chat/PyodideFileNav.svelte`

- [x] [tid_codespan_open_behavior] Make sandbox file codespans open files instead of copying paths

  **What to do**: Update `CodespanToken` so valid sandbox paths under `/mnt/uploads/...` invoke the new sandbox open-path flow instead of clipboard copy. Preserve the current copy behavior and success toast for all non-sandbox codespans.
  **Must NOT do**: Must NOT make every inline code span navigational. Must NOT remove copy affordance from non-file code. Must NOT depend on backend file IDs or URLs.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: narrow component interaction change after routing infrastructure exists.
  - Skills: [`test`] — reason: component regression behavior is the main risk.
  - Omitted: [`playwright`] — reason: browser proof belongs after message-surface work is complete.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: none | Blocked By: `tid_matcher_contract`, `tid_sandbox_open_routing`

  **References**:
  - Pattern: `src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens/CodespanToken.svelte:17` — current click-to-copy behavior.
  - Pattern: `src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens.svelte:104` — call site for codespan rendering.
  - Pattern: `src/lib/utils/index.ts:1993` — display-file routing helper to reuse or mirror.

  **Acceptance Criteria**:
  - [ ] Clicking a valid `/mnt/uploads/...` codespan opens the sandbox file pane instead of copying the text.
  - [ ] Clicking a non-path codespan still copies to clipboard and shows the existing success affordance.
  - [ ] Keyboard interaction or accessibility semantics remain valid for the new open-file behavior.
  - [ ] The change works for nested sandbox paths and filenames containing spaces.

  **QA Scenarios**:

  ```
  Scenario: Sandbox path codespan opens file instead of copying
    Tool: Bash
    Steps: Run `pnpm test -- --runInBand src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens/CodespanToken.test.*`
    Expected: Click on `/mnt/uploads/report.md` dispatches sandbox-file open behavior, not clipboard copy.
    Evidence: .sisyphus/evidence/task-tid_codespan_open_behavior-tests.txt

  Scenario: Ordinary codespan still copies text
    Tool: Bash
    Steps: Run the same suite with regression cases for `pip install foo` and `/tmp/report.md`.
    Expected: Clipboard copy assertions still pass for non-sandbox codespans.
    Evidence: .sisyphus/evidence/task-tid_codespan_open_behavior-regression.txt
  ```

  **Commit**: YES | Message: `feat(chat): open sandbox file codespans in files pane` | Files: `src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens/CodespanToken.svelte`, related tests

- [x] [tid_file_chip_surface] Render sandbox file references as explicit file artifacts

  **What to do**: Add a dedicated file-chip rendering path for sandbox-generated files so assistant output no longer relies on raw inline path text. Chips must clearly indicate a generated local file and expose at least open + download actions. Use the sandbox open-path flow for primary interaction.
  **Must NOT do**: Must NOT invent a generalized entity system or refactor all markdown rendering. Must NOT remove support for plain text fallback when no valid sandbox path is present.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: this is primarily message-surface UX and affordance design.
  - Skills: [`frontend-ui-ux`] — reason: needs clear visual treatment without over-designing the stack.
  - Omitted: [`deep`] — reason: no architecture overhaul is needed for this slice.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: none | Blocked By: `tid_matcher_contract`, `tid_sandbox_open_routing`

  **References**:
  - Pattern: `src/lib/components/chat/Messages/Markdown/MarkdownInlineTokens.svelte:75` — existing link token rendering path.
  - Pattern: `src/lib/components/common/FileItem.svelte:54` — reusable file-card interaction ideas for open/download affordances.
  - Pattern: `src/lib/components/chat/PyodideFileNav.svelte:419` — existing download action in the sandbox files pane.
  - Pattern: `src/lib/components/layout/FilesModal.svelte:132` — backend file viewer open pattern to mirror at the surface level.

  **Acceptance Criteria**:
  - [ ] Sandbox-generated file references render as explicit file chips or equivalent artifact UI, not only as raw inline code.
  - [ ] Clicking the primary chip action opens the file in `PyodideFileNav`.
  - [ ] A download action is visible and works for sandbox files.
  - [ ] Invalid or stale sandbox references fall back to a clear disabled/not-found state instead of a broken open action.
  - [ ] Plain markdown paths that are not valid sandbox files continue rendering normally.

  **QA Scenarios**:

  ```
  Scenario: Sandbox file chip renders and opens the file pane
    Tool: Bash
    Steps: Run `pnpm test -- --runInBand src/lib/components/chat/Messages/Markdown/SandboxFileToken.test.*`
    Expected: Valid sandbox path renders a chip with open/download actions and dispatches sandbox open on click.
    Evidence: .sisyphus/evidence/task-tid_file_chip_surface-tests.txt

  Scenario: Invalid sandbox path shows safe fallback
    Tool: Bash
    Steps: Run the same suite with malformed or stale paths.
    Expected: Component falls back cleanly without broken click behavior.
    Evidence: .sisyphus/evidence/task-tid_file_chip_surface-fallback.txt
  ```

  **Commit**: YES | Message: `feat(chat): render sandbox generated file chips` | Files: chat markdown rendering components for sandbox file artifacts and their tests

- [x] [tid_preview_parity] Expand sandbox preview support for common generated file types

  **What to do**: Upgrade `PyodideFileNav` so sandbox-generated PDFs, audio, video, JSON/markdown/csv/common text, and other high-value artifact types use richer inline previews, reusing `FilePreview` props/branches where practical rather than inventing a separate viewer system.
  **Must NOT do**: Must NOT merge `FileNav` and `PyodideFileNav` architectures wholesale. Must NOT block this task on perfect parity for every binary type. Must NOT change backend file viewers.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: medium-complexity UI/data-shaping work across several preview types.
  - Skills: [`frontend-ui-ux`] — reason: needs careful reuse of current preview surfaces without regressions.
  - Omitted: [`deep`] — reason: this is breadth of preview handling, not long-range architecture.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: none | Blocked By: `tid_sandbox_open_routing`

  **References**:
  - Pattern: `src/lib/components/chat/PyodideFileNav.svelte:185` — current file-read path only sets text/image previews.
  - Pattern: `src/lib/components/chat/FileNav/FilePreview.svelte:22` — accepted preview prop contract.
  - Pattern: `src/lib/components/chat/FileNav/FilePreview.svelte:108` — existing HTML/path-based serving branches for richer previews.
  - Pattern: `src/lib/components/common/FileItemModal.svelte:67` — preview type detection used for backend files.

  **Acceptance Criteria**:
  - [ ] Sandbox PDFs preview inline instead of only showing binary fallback.
  - [ ] Sandbox audio/video files preview inline with native media controls.
  - [ ] Existing text/image preview behavior remains intact.
  - [ ] Unsupported binary files still download cleanly and present a clear fallback state.

  **QA Scenarios**:

  ```
  Scenario: Common sandbox file types preview inline
    Tool: Bash
    Steps: Run `pnpm test -- --runInBand src/lib/components/chat/FileNav/FilePreview.test.* src/lib/components/chat/PyodideFileNav.test.*`
    Expected: PDF/audio/video/text preview branches succeed for sandbox-backed file data.
    Evidence: .sisyphus/evidence/task-tid_preview_parity-tests.txt

  Scenario: Unsupported binary still downloads without preview crash
    Tool: Bash
    Steps: Include a binary fixture outside the supported set in the same suite.
    Expected: UI shows safe fallback and download path remains available.
    Evidence: .sisyphus/evidence/task-tid_preview_parity-binary.txt
  ```

  **Commit**: YES | Message: `feat(chat): improve pyodide file preview support` | Files: `src/lib/components/chat/PyodideFileNav.svelte`, `src/lib/components/chat/FileNav/FilePreview.svelte`, preview tests and fixtures

- [x] [tid_publish_flow] Add explicit publish-to-backend flow for durable generated files

  **What to do**: Add an explicit user or flow-driven action that takes a selected sandbox file, uploads/registers it into backend Open WebUI file storage, creates the necessary backend `file` record (and chat attachment linkage if supported), and then exposes the durable file through the existing backend file surface.
  **Must NOT do**: Must NOT auto-publish every generated file. Must NOT expose sandbox paths as backend URLs without successful publication. Must NOT redesign ownership, quota, or storage policy beyond the minimum explicit publish flow.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: crosses frontend artifact UX and backend durable-file registration semantics.
  - Skills: [`api-design`] — reason: needs clean explicit boundary between sandbox file bytes and backend file registration.
  - Omitted: [`visual-engineering`] — reason: the hard part is the flow/contract, not styling.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: none | Blocked By: `tid_file_chip_surface`

  **References**:
  - Pattern: `backend/open_webui/routers/files.py:723` — backend content-serving route for durable files.
  - Pattern: `src/lib/components/common/FileItem.svelte:63` — open backend file content via `/files/{id}/content`.
  - Pattern: `src/lib/components/layout/FilesModal.svelte:132` — backend file viewer launch flow.
  - Pattern: DB investigation result — sandbox artifacts had no `file` or `chat_file` records, proving publication must be explicit.

  **Acceptance Criteria**:
  - [ ] User can explicitly publish a sandbox-generated file into backend Open WebUI file storage.
  - [ ] Successful publish yields a durable backend file reference accessible via the existing backend file route.
  - [ ] Published files can be opened through the existing backend file viewer surfaces.
  - [ ] Failed publish leaves the sandbox file intact and shows a clear error state.

  **QA Scenarios**:

  ```
  Scenario: Publish sandbox file into backend storage
    Tool: Playwright / Bash
    Steps: Generate a sandbox file, invoke publish, then verify the resulting artifact opens through the existing backend file viewer and resolves to the backend content route.
    Expected: Durable file record exists, UI opens the published file, and the backend route serves it successfully.
    Evidence: .sisyphus/evidence/task-tid_publish_flow-playwright.txt

  Scenario: Publish failure leaves local artifact usable
    Tool: Playwright / Bash
    Steps: Simulate or force a backend publish failure while the sandbox file still exists.
    Expected: Error is surfaced clearly and the sandbox file remains openable/downloadable from `PyodideFileNav`.
    Evidence: .sisyphus/evidence/task-tid_publish_flow-failure.txt
  ```

  **Commit**: YES | Message: `feat(chat): add explicit publish flow for sandbox files` | Files: frontend artifact actions, backend file registration path(s), tests covering durable publication

## Final Verification Wave (MANDATORY — after ALL implementation tasks) <!-- oc:id=sec_final_verification -->

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.

- [x] [fid_plan_compliance] Plan Compliance Audit — oracle
- [x] [fid_code_quality] Code Quality Review — unspecified-high
- [x] [fid_real_qa] Real Manual QA — unspecified-high (+ playwright if UI)
- [x] [fid_scope_fidelity] Scope Fidelity Check — deep

## Commit Strategy <!-- oc:id=sec_961c1d -->

- Commit each task as an independently shippable slice.
- Suggested sequence:
  - `test(chat): lock sandbox path detection behavior`
  - `feat(chat): route sandbox file paths into pyodide files pane`
  - `feat(chat): open sandbox file codespans in files pane`
  - `feat(chat): render sandbox generated file chips`
  - `feat(chat): improve pyodide file preview support`
  - `feat(chat): add explicit publish flow for sandbox files`
- Do not combine phase 1 navigation work with preview parity or publish flow.

## Success Criteria <!-- oc:id=sec_05ed58 -->

- Users no longer need to manually inspect or copy `/mnt/uploads/...` paths to access generated files.
- Clicking a sandbox-generated file reference reliably opens the correct file surface.
- View/download works immediately for local artifacts.
- Durable backend file access exists only after explicit publish.
- Existing inline code copy semantics remain intact for non-file codespans.
