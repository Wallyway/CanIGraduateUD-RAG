# Frontend Architecture & State Management: Can I Graduate UD?

This document provides an exhaustive technical specification of the state architecture, streaming lifecycle, client persistence, device fingerprinting, and administrative modules of the **Can I Graduate UD?** Next.js 14 frontend.

---

## 1. System Architecture Overview

The frontend is built on Next.js 14 App Router and acts as the presentation and interaction layer for the normative RAG backend serving the Faculty of Engineering at Universidad Distrital Francisco José de Caldas.

```
+-----------------------------------------------------------------------------------+
|                                Browser Client                                    |
|                                                                                   |
|  +---------------------------+       +-----------------------------------------+  |
|  |   Student Chat Portal     |       |            Admin CRM Portal             |  |
|  |   (app/page.tsx)          |       |            (app/admin/page.tsx)         |  |
|  |                           |       |                                         |  |
|  | - WebGL Background        |       | - AdminSidebar (badges & drawer)        |  |
|  | - ChatInterface           |       | - Tab Router (?tab=analytics|triage...) |  |
|  | - Agent Reasoning Trace   |       | - AnalyticsDashboardModule (Recharts)   |  |
|  | - CitationBadge Excerpts  |       | - EmailTriageModule (Review & Ingest)   |  |
|  | - Virtual Queue Banner    |       | - KnowledgeBaseModule (Docs & Chunks)   |  |
|  | - Feedback Modal          |       | - SessionFeedbackModule (Ratings)       |  |
|  +-------------+-------------+       | - SettingsGuardrailsModule (Toggles)    |  |
|                |                     +--------------------+--------------------+  |
|                |                                          |                       |
|  +-------------v------------------------------------------v--------------------+  |
|  |                   Client Infrastructure Layer (src/lib/)                    |  |
|  |  - api.ts: streamChat() [SSE parser, pings, retry], admin API endpoints     |  |
|  |  - storage.ts: LocalStorage (chat history, JWT token), SessionStorage       |  |
|  |  - utils.ts: cn() class mergers                                             |  |
+----------------+------------------------------------------+-----------------------+
                 |                                          |
                 | HTTP POST /api/v1/chat/stream            | REST /api/v1/admin/*
                 | Headers: X-Device-Id, X-MAC-Address      | Headers: Bearer <JWT>
                 v                                          v
+-----------------------------------------------------------------------------------+
|                             FastAPI Backend (Port 8000)                           |
|  - VirtualQueueManager (concurrency permits, keepalive : ping)                    |
|  - RAG Pipeline (PostgreSQL 16, ChromaDB, Dual-Layer Cache, OpenRouter LLMs)      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Chat Lifecycle & Interaction State Machine

The student chat experience is centered in `src/components/ChatInterface.tsx` and follows a discrete finite state machine:

```
[ IDLE / HERO STATE ]
        |
        | User inputs query (ai-prompt-box or suggestion chip)
        v
[ SUBMITTED ] ------------> Creates optimistic user message & empty assistant placeholder
        |                   Builds initial reasoning trace (TraceNode[])
        v
[ CONNECTING ] -----------> POST /api/v1/chat/stream with X-Device-Id & X-MAC-Address
        |
        +----------------------------+
        |                            | Backend concurrency saturated
        |                            v
        |                  [ QUEUED (Virtual Queue) ]
        |                            |
        |                            | Displays: "En cola: #N de la fila (~Ss)..."
        |                            | Filters: ": ping\n\n" heartbeat comments
        |                            v
        |                  [ QUEUE READY ]
        |                            |
        +<---------------------------+ Permitted by VirtualQueueManager
        |
        v
[ STREAMING ] ------------> Consumes SSE frames:
        |                   - "token": batches updates via requestAnimationFrame
        |                   - "citations": dedupes and links normative sources
        |
        +-----------------------------------------+
        |                                         |
        | Normal stream termination               | Saturated / Aborted / 503
        v                                         v
[ COMPLETED ]                             [ ERROR / RETRYABLE ]
        |                                         |
        | Updates durationSeconds                 | Renders 1-Click Retry button
        | Persists to LocalStorage                | User clicks -> re-executes handleSend
        | Enables FeedbackModal trigger           |
        v                                         v
[ READY FOR NEXT QUERY ]                  [ RETRY EXECUTED ]
```

### 2.1 State Variables in `ChatInterface.tsx`

| State Variable | Type | Responsibility |
|---|---|---|
| `messages` | `ChatMessage[]` | Conversation thread history rendered in the UI. |
| `isLoading` | `boolean` | Indicates active backend processing; disables input submit. |
| `activeAssistantId` | `string \| null` | ID of the currently streaming assistant message card. |
| `queueInfo` | `{ position: number; estimated_seconds: number } \| null` | Holds queue depth and wait duration. Null when actively streaming. |
| `sessionId` | `string` | Ephemeral session UUID stored in `sessionStorage` for analytics attribution. |
| `isFeedbackModalOpen` | `boolean` | Controls visibility of the student feedback modal dialog. |

### 2.2 Smooth Batching via `requestAnimationFrame`

High-throughput LLM streaming can emit dozens of tokens per second. Directly updating React state on every token triggers excessive DOM reconciliations. `ChatInterface.tsx` uses `requestAnimationFrame` (rAF) batching to throttle rendering:

```typescript
let currentResponseText = "";
let rafId: number | null = null;

const scheduleUpdate = () => {
  if (rafId !== null) return;
  rafId = requestAnimationFrame(() => {
    rafId = null;
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantMsgId
          ? { ...msg, content: currentResponseText }
          : msg
      )
    );
  });
};
```

When the stream completes (`onDone`), any pending `rafId` is cancelled and the full final message is committed to `localStorage`.

---

## 3. Resilient SSE Stream Parser (`src/lib/api.ts`)

The `streamChat` function provides a zero-dependency SSE parser built directly on the browser's `ReadableStream` API.

### 3.1 Packet Reconstruction & Delimiter Parsing

Network packets often arrive fragmented across TCP frames. The parser buffers incoming bytes using `TextDecoder` and continuously splits on double-newlines (`\n\n`):

```typescript
const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split("\n\n");
  buffer = lines.pop() || ""; // Retain incomplete trailing chunk in buffer

  for (const block of lines) {
    const blockLines = block.split("\n");
    for (const rawLine of blockLines) {
      const trimmed = rawLine.trim();

      // 1. Skip SSE comments (e.g., ": ping")
      if (!trimmed || trimmed.startsWith(":")) continue;

      // 2. Only process standard SSE data lines
      if (!trimmed.startsWith("data:")) continue;

      const dataStr = trimmed.replace(/^data:\s*/, "").trim();

      // 3. Handle stream completion marker
      if (dataStr === "[DONE]") {
        onDone();
        return;
      }

      // 4. Parse JSON payload
      try {
        const parsed = JSON.parse(dataStr);
        if (parsed.type === "token" && parsed.content) {
          onToken(parsed.content);
        } else if (parsed.type === "citations" && parsed.citations) {
          onCitations(parsed.citations);
        } else if (parsed.type === "queue" && onQueue) {
          onQueue({
            position: Number(parsed.position) || 1,
            estimated_seconds: Number(parsed.estimated_seconds) || 2,
          });
        } else if (parsed.type === "queue_ready" && onQueue) {
          onQueue({ position: 0, estimated_seconds: 0 });
        }
      } catch (e) {
        // Suppress JSON parse errors on malformed partial stream frames
      }
    }
  }
}
```

### 3.2 Keep-Alive Comment Frame Filtering

The FastAPI backend issues periodic `: ping\n\n` comments every 5 seconds to keep intermediary reverse proxies (Nginx, Cloudflare) from terminating idle connections during complex vector retrievals or queue delays.

The parser explicitly discards lines where `trimmed.startsWith(":")`, preventing keep-alive heartbeats from corrupting message text or causing JSON parse failures.

### 3.3 1-Click Retry Mechanism

When the backend queue exceeds its ceiling capacity (100 concurrent waiting connections), or when LLM upstream providers return rate limits, the backend returns an HTTP 503 or an informational error message containing phrases like *"reintenta"* or *"volumen muy alto"*.

`ChatInterface.tsx` inspects completed messages:
```tsx
{msg.content && !isLoading && (msg.content.includes("reintenta") || msg.content.includes("volumen muy alto")) && (
  <button
    onClick={() => {
      const idx = messages.findIndex((m) => m.id === msg.id);
      const prevUserMsg = idx > 0 ? messages[idx - 1] : null;
      if (prevUserMsg && prevUserMsg.role === "user" && prevUserMsg.content) {
        handleSend(prevUserMsg.content);
      }
    }}
    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-xs font-medium"
  >
    <span>🔄</span>
    <span>Reintentar consulta con 1 clic</span>
  </button>
)}
```
This guarantees that users never lose their prompt context during high-load traffic spikes.

---

## 4. Virtual Queue UX & Concurrency Management

The backend enforces a strict semaphore limit of 150 concurrent LLM streams and places excess queries into an in-memory `VirtualQueueManager`.

### 4.1 Queue Banner Dynamics

When a student's request is queued, the backend emits:
```
data: {"type": "queue", "position": 4, "estimated_seconds": 8}\n\n
```

1. **Detection**: `streamChat` triggers `onQueue({ position: 4, estimated_seconds: 8 })`.
2. **Banner Mounting**: `ChatInterface.tsx` renders an amber waiting banner inside the assistant's message container:
   ```tsx
   <div className="mb-3 px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-center gap-2">
     <Clock className="w-4 h-4 animate-spin" />
     <span>En cola: #{queueInfo.position} de la fila (espera estimada: ~{queueInfo.estimated_seconds}s)...</span>
   </div>
   ```
3. **Heartbeat Maintenance**: The backend emits `: ping\n\n` comments every 5s while the request waits in the queue, keeping the HTTP socket open.
4. **Permit Acquisition**: Once a concurrency slot opens, the backend emits `{"type": "queue_ready"}`. The frontend resets `queueInfo` to `null` and seamlessly shifts into token streaming without layout flickering.

---

## 5. Client Persistence & Device Fingerprinting

Client state is managed through `src/lib/storage.ts` and `src/lib/api.ts` across `localStorage` and `sessionStorage`.

### 5.1 Storage Keys & Schema Reference

| Storage Engine | Key Name | Data Type | Purpose |
|---|---|---|---|
| `localStorage` | `can_i_graduate_ud_chat_history` | `ChatMessage[]` | Persistent student conversation thread. Survives browser reloads. |
| `localStorage` | `can_i_graduate_ud_admin_token` | `string` | Administrative JWT token for authenticated CRM actions. |
| `localStorage` | `ud_client_device_id` | `string` | Randomly generated client UUID for persistent device tracking. |
| `localStorage` | `ud_client_mac` | `string` | Deterministic synthetic hardware signature hash. |
| `sessionStorage` | `can_i_graduate_session_id` | `string` | Ephemeral session token refreshed on browser tab restarts. |

### 5.2 Message Entity Schema (`ChatMessage`)

```typescript
export interface ChatMessage {
  id: string;                     // Timestamp ID or UUID
  role: "user" | "assistant";     // Message emitter
  content: string;                // Rendered Markdown content
  citations?: Array<{             // Normative legal citations
    title: string;                // e.g. "Acuerdo 028 de 2017"
    resolution: string;           // e.g. "Resolución 035"
    article: string;              // e.g. "Artículo 12 - Pasantía"
    source_type: string;          // e.g. "acuerdo" | "resolucion"
    excerpt: string;              // Official verbatim legal excerpt
  }>;
  durationSeconds?: number;       // Elapsed streaming duration
  trace?: TraceNode[];            // Reasoning steps (search, evaluate, answer)
  timestamp: string;              // ISO-8601 string
}
```

### 5.3 Hardware Fingerprinting Engine

To mitigate prompt abuse and enforce IP/device penalties without requiring mandatory student logins, `src/lib/api.ts` computes two client identifiers transmitted on every request:

1. **Device UUID (`getDeviceId`)**:
   Generates a persistent identifier (`dev_<base36_random>_<timestamp>`) stored in `localStorage.ud_client_device_id`.
2. **Synthetic Hardware Signature (`getClientMac`)**:
   Generates a deterministic 12-character hex MAC string (`XX:XX:XX:XX:XX:XX`) based on a bitwise shift-xor hash of:
   - Screen geometry (`width`, `height`, `colorDepth`)
   - CPU thread concurrency (`navigator.hardwareConcurrency`)
   - User Agent string
   - Generation timestamp seed

```typescript
export function getClientMac(): string {
  if (typeof window === "undefined") return "00:00:00:00:00:00";
  let mac = localStorage.getItem("ud_client_mac");
  if (!mac) {
    const screenData = `${window.screen?.width || 1920}x${window.screen?.height || 1080}x${window.screen?.colorDepth || 24}`;
    const cores = navigator.hardwareConcurrency || 4;
    let hash = 0;
    const str = `${screenData}_${cores}_${navigator.userAgent}_${Date.now()}`;
    for (let i = 0; i < str.length; i++) {
      hash = (hash << 5) - hash + str.charCodeAt(i);
      hash |= 0;
    }
    const hex = (Math.abs(hash).toString(16) + "abcdef0123456789").substring(0, 12);
    mac = (hex.match(/.{1,2}/g) || ["00", "11", "22", "33", "44", "55"]).join(":").toUpperCase();
    localStorage.setItem("ud_client_mac", mac);
  }
  return mac;
}
```

---

## 6. Admin CRM Architecture & Modules

The administration portal is located in `src/app/admin/` and serves curriculum directors, academic coordinators, and system administrators.

### 6.1 Authentication Gatekeeper (`AdminLayoutInner`)

Located in `src/app/admin/layout.tsx`:
- Inspects `getAdminToken()` on initial mount and route transitions.
- If no token is present and the current pathname is not `/admin/login`, redirects immediately to `/admin/login`.
- If an API request returns an HTTP 401 Unauthorized, `clearAdminToken()` is invoked and the user is redirected to the login view.
- Provides top navigation with breadcrumbs, system status badges, and mobile sidebar drawer toggle.

### 6.2 URL Tab Routing

The admin portal organizes its functionality into 5 distinct modules accessible through the URL query parameter `?tab=<key>` in `src/app/admin/page.tsx`:

```typescript
type TabKey = "analytics" | "triage" | "knowledge" | "settings" | "feedback";
```

Switching tabs updates the browser URL without full page reload via `router.replace(`/admin?tab=${key}`, { scroll: false })`, supporting deep linking and browser back/forward navigation.

### 6.3 Module Specifications

#### 1. `AnalyticsDashboardModule`
- **Location**: `src/components/admin/AnalyticsDashboardModule.tsx` (1,007 lines)
- **Features**:
  - Metric summary cards: Total queries, average response latency, token throughput, cache hit rates.
  - Interactive charts powered by `recharts`: Time-series query volume (area chart), hourly traffic distribution (bar chart), top cited normative resolutions (horizontal bar chart).
  - Sentiment distribution and feedback rating breakdown.

#### 2. `EmailTriageModule`
- **Location**: `src/components/admin/EmailTriageModule.tsx` (1,320 lines)
- **Features**:
  - Institutional inbox monitoring incoming queries submitted to `canigraduateud@gmail.com`.
  - Email detail view displaying headers, parsed body, and file attachments.
  - Markdown extraction engine allowing coordinators to convert email inquiries into normative QA pairs.
  - One-click actions: Approve & Ingest into ChromaDB vector store, Reject/Discard, or Draft Response.
  - Dispatches `onDataChanged={fetchStats}` callback to update sidebar counters in real time.

#### 3. `KnowledgeBaseModule`
- **Location**: `src/components/admin/KnowledgeBaseModule.tsx` (1,192 lines)
- **Features**:
  - Document catalog listing Acuerdos, Resoluciones, and Circulares.
  - Vector chunk browser allowing inspection of chunk boundaries, token sizes, and metadata.
  - Integrated modal dialog supporting dual upload modes:
    - PDF document upload with automatic server-side text extraction.
    - Direct Markdown authoring for immediate institutional notices.
  - Interactive semantic probe testing similarity against ChromaDB vectors.

#### 4. `SessionFeedbackModule`
- **Location**: `src/components/admin/SessionFeedbackModule.tsx` (510 lines)
- **Features**:
  - Student feedback review console grouped by rating (1–5 stars) and issue category (`sugerencia`, `informacion_imprecisa`, `error_tecnico`, `general`).
  - Conversation transcript inspector linked by `session_id`.
  - Disposition actions: Mark as Resolved, Flag for Knowledge Base Update, or Archive.

#### 5. `SettingsGuardrailsModule`
- **Location**: `src/components/admin/SettingsGuardrailsModule.tsx` (311 lines)
- **Features**:
  - System toggles: Autonomous document ingestion switch, semantic similarity threshold sliders.
  - Security gates: Blocked topic keywords, forbidden prompt regexes.
  - IP and device rate-limiting controls, client ban list, and penalty release controls.
