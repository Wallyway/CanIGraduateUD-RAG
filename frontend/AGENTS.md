# Frontend Agent Guidelines: Can I Graduate UD?

Authoritative operational handbook for AI agents and engineers working on the Next.js 14 frontend of **Can I Graduate UD?** (institutional normative RAG assistant for Universidad Distrital Francisco José de Caldas).

## 1. Essential Developer Commands

All commands must be executed from the `frontend/` directory using `pnpm` (`pnpm@9.5.0` enforced):

```bash
cd frontend
pnpm dev                        # Run Next.js App Router dev server on http://localhost:3000
./node_modules/.bin/next build  # Compile production build (checks TypeScript + ESLint)
pnpm start                      # Start production standalone server
pnpm lint                       # Execute ESLint validation checks
```

## 2. Core Technology Stack & Versions

- **Framework**: Next.js 14.2.5 (App Router, Server & Client Component boundaries)
- **UI & Runtime**: React 18.3.1, ReactDOM 18.3.1 (React Portal via `createPortal`), TypeScript 5.5.2 (strict mode, `@/*` -> `./src/*`)
- **Telemetry & Web Vitals**: `@vercel/analytics/next` 1.6.1 mounted in `layout.tsx`
- **Styling**: Tailwind CSS 3.4.4, PostCSS 8.4.38, Autoprefixer 10.4.19
- **WebGL Background**: `ogl` 1.0.11 (GPU fluid mesh shader in `MoltenMetal.tsx`)
- **Animation & Icons**: Framer Motion 13.2.0, Lucide React 0.400.0
- **Markdown & Charts**: React Markdown 9.0.1, Remark GFM 4.0.0, Recharts 3.10.1
- **Headless Primitives**: `@radix-ui/react-dialog` 1.1.23, `@radix-ui/react-tooltip` 1.2.16

## 3. Environment Configuration

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend FastAPI service endpoint |

## 4. Directory Layout & Layer Responsibilities

```
frontend/src/
├── app/                      # Next.js App Router (pages, layouts, metadata)
│   ├── globals.css           # CSS variables, Tailwind directives, custom scrollbars
│   ├── layout.tsx            # RootLayout: Vercel <Analytics />, SEO & JSON-LD schemas
│   ├── page.tsx              # Student chat entrypoint (mounts <ChatInterface />)
│   ├── robots.ts, sitemap.ts # Dynamic SEO & bot directives
│   └── admin/                # Institutional CRM portal
│       ├── layout.tsx        # Auth gatekeeper, sidebar drawer, breadcrumb
│       ├── page.tsx          # Tabbed dashboard (analytics, triage, KB, settings, feedback)
│       ├── login/page.tsx    # Admin credentials login form
│       └── documents/page.tsx# Direct knowledge base document route
├── components/               # Active UI components (0 orphans)
│   ├── ChatInterface.tsx     # Student chat, SSE streaming, ban enforcement, retry
│   ├── CitationBadge.tsx     # Normative citation chips with createPortal modal
│   ├── MoltenMetal.tsx       # Dynamic WebGL fluid background (ogl shader)
│   ├── admin/                # 6 modular panels (Sidebar, Analytics, Triage, KB, Feedback, Settings)
│   └── ui/                   # Primitives: agent-trace.tsx, ai-prompt-box.tsx
└── lib/                      # Infrastructure & utilities
    ├── api.ts                # HTTP & SSE client, ban checking (/ban-status), fingerprinting
    ├── storage.ts            # LocalStorage & SessionStorage helpers
    └── utils.ts              # cn() classnames merger (clsx + tailwind-merge)
```

## 5. SSE Streaming Protocol & Cross-Layer Contract

Chat communication streams from `POST /api/v1/chat/stream`:
- **Client Fingerprint Headers**:
  - `X-Device-Id`: Client UUID persisted in `localStorage.ud_client_device_id`.
  - `X-MAC-Address`: Deterministic hardware hash generated in `src/lib/api.ts:getClientMac()`.
- **Payload Structure**: `{"query": string, "history": Array<{ role: string, content: string }>}`
- **SSE Frame Handling (`streamChat` in `src/lib/api.ts`)**:
  - `data: {"type": "queue", "position": N, "estimated_seconds": S}`: Renders queue banner.
  - `data: {"type": "queue_ready"}`: Concurrency permit granted; transitions to streaming.
  - `data: {"type": "token", "content": string}`: Real-time tokens scheduled via `requestAnimationFrame`.
  - `data: {"type": "citations", "citations": [...]}`: Verified legal sources with article excerpts.
  - `data: {"type": "security_ban", "remaining_seconds": N, "reason": string}`: 24h ban event.
  - `: ping`: FastAPI keep-alive comments sent every 5s; explicitly skipped by parser.
  - `data: [DONE]`: Terminal signal ending stream and invoking `onDone()`.

```typescript
// Typical SSE consumption pattern in ChatInterface.tsx
await streamChat(text, historyPayload,
  (token) => { currentText += token; scheduleUpdate(); },
  (citations) => { setCitations(dedupe(citations)); },
  () => { setIsLoading(false); saveStoredChatHistory(messages); },
  (err) => { setIsLoading(false); displayRetryError(err); },
  (queue) => { setQueueInfo(queue.position > 0 ? queue : null); },
  (ban) => { setBanState({ isBanned: true, remainingSeconds: ban.remaining_seconds, reason: ban.reason }); }
);
```

- **Backend Status Codes & Retry**:
  - `401 Unauthorized`: Session expired; redirect to `/admin/login`.
  - `403 Forbidden`: Client banned for 24h (synced with `/api/v1/chat/ban-status`).
  - `429 Too Many Requests`: Rate limiter or temporary IP throttle triggered.
  - `503 Service Unavailable`: Concurrency queue saturated; `ChatInterface.tsx` renders 1-click retry.

## 6. Client State & LocalStorage Schema

- `can_i_graduate_ud_chat_history`: Serialized `ChatMessage[]` (id, role, content, citations, trace, duration).
- `can_i_graduate_ud_admin_token`: Admin JWT bearer string for protected CRM endpoints.
- `can_i_graduate_session_id`: SessionStorage ID used for feedback attribution.
- `ud_banned_until`: Ban expiration timestamp (ms string); verified on mount and synchronized with `/ban-status`.
- `ud_banned_reason`: Explanatory security violation reason displayed on the ban card.
- `ud_client_device_id`: Persistent client UUID for device tracking.
- `ud_client_mac`: Synthetic hardware MAC address signature.

## 7. Admin CRM Tab Routing

The admin interface (`src/app/admin/page.tsx`) uses URL search parameter tab synchronization:
- `?tab=analytics`: System latency, query volume, resolution rankings (`AnalyticsDashboardModule`)
- `?tab=triage`: Institutional email inbox, markdown approval, ingestion (`EmailTriageModule`)
- `?tab=knowledge`: Normative catalog, vector chunk browser, manual uploader (`KnowledgeBaseModule`)
- `?tab=settings`: Ingestion toggle, similarity thresholds, guardrails (`SettingsGuardrailsModule`)
- `?tab=feedback`: Student feedback review console and disposition controls (`SessionFeedbackModule`)

## 8. Client vs. Server Component Conventions

- **Server Components (Default)**: Use for static/metadata routes (`app/layout.tsx`, `app/page.tsx`, `robots.ts`, `sitemap.ts`). Cannot use hooks or browser APIs.
- **Client Components (`"use client"`)**: Mandatory at line 1 for interactive UI (`ChatInterface.tsx`, `MoltenMetal.tsx`, admin modules) due to WebGL rendering, SSE streams, and `localStorage`.

## 9. Dual-Theme Design & Styling Tokens

- **Student Portal**: Dark luxury aesthetic (`zinc-950`, `white/[0.08]` borders, `amber-400` highlights, WebGL fluid canvas).
- **Admin CRM**: High-density clean workspace (`#FAF8F5` canvas, stone borders, `orange-600` accents) for reviewing large institutional datasets.
- **Brand Colors**: `ud.red` (`#8B1E1E`), `ud.gold` (`#D4A017`), `ud.navy` (`#0F1E36`).
- **Scrollbars**: Custom dark webkit scrollbar styles defined in `globals.css` lines 34–48.

## 10. Accessibility & Micro-Interactions

- Use `aria-live="polite"` on streaming tokens and dynamic queue banners.
- Implement dialogs with `@radix-ui/react-dialog` for focus trapping, backdrop blur, and ESC exit.
- Render modal overlays via React Portal (`createPortal(modal, document.body)`) to avoid z-index or overflow clipping.
- Ensure WCAG AA contrast (`neutral-200` on dark surfaces) and semantic markup (`<main>`, `<header>`).

## 11. Rules for AI Agents Modifying Frontend

- **Zero Orphans**: Never leave unreferenced components, CSS keyframes, or dead imports.
- **Build Verification**: Always verify changes by running `./node_modules/.bin/next build`.
- **No Direct Mutation**: Respect `storage.ts` abstraction for all `localStorage` access.
- **Safe WebGL Cleanup**: Always call `gl.getExtension('WEBGL_lose_context')?.loseContext()` on unmount.
- **Portal Rendering**: Always render floating citation details via `createPortal` to preserve layout isolation.

## 12. Quick Start for Common Tasks

- **Add New Admin Module**:
  1. Create `src/components/admin/MyNewModule.tsx` with `"use client"`.
  2. Register module in `src/app/admin/page.tsx` within `TabKey` and render branch.
  3. Add navigation entry in `src/components/admin/AdminSidebar.tsx`.
- **Modify Normative Citations**:
  - Update `CitationBadge.tsx` for chip rendering, `createPortal` modal popover excerpts, and PDF download links.
- **Tune WebGL Canvas**:
  - Adjust shader uniforms (`speed`, `glow`, `swirl`, `colorMode`) in `MoltenMetal.tsx` props.

## 13. Modular Documentation Index

For deep architectural analyses, state diagrams, and component catalogs:
- **`docs/architecture_and_state.md`**: Chat lifecycle, SSE parser state machine, virtual queue UX, LocalStorage persistence, device fingerprinting, admin modules.
- **`docs/components_and_styling.md`**: Component catalog, Tailwind design tokens, WebGL MoltenMetal pipeline, modal dialogs, accessibility guidelines.
