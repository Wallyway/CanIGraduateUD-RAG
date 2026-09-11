# Frontend Components & Styling Guide: Can I Graduate UD?

This document serves as the comprehensive technical reference for the UI component catalog, styling design tokens, WebGL fluid background shaders, and accessibility standards of the **Can I Graduate UD?** Next.js 14 frontend.

---

## 1. Component Hierarchy & Directory Organization

All active UI components reside in `frontend/src/components/`:

```
frontend/src/components/
├── ChatInterface.tsx           # Primary student chat interface & orchestration
├── CitationBadge.tsx           # Normative citation chips with excerpt popovers
├── MoltenMetal.tsx             # Interactive WebGL fluid background (ogl shader)
├── admin/                      # Administrative CRM module catalog
│   ├── AdminSidebar.tsx        # Navigation sidebar with responsive drawer & badges
│   ├── AnalyticsDashboardModule.tsx  # Latency, throughput & citation charts (Recharts)
│   ├── EmailTriageModule.tsx   # Institutional inbox review & RAG ingestion
│   ├── KnowledgeBaseModule.tsx # Normative document catalog & vector chunks browser
│   ├── SessionFeedbackModule.tsx # Student rating & feedback review console
│   └── SettingsGuardrailsModule.tsx # Autonomous mode, thresholds, guardrail settings
└── ui/                         # Atomic interface primitives
    ├── agent-trace.tsx         # Multi-phase agent reasoning nodes & PixelDotsLoader
    └── ai-prompt-box.tsx       # Auto-resizing textarea with keyboard shortcuts
```

---

## 2. Production Component Catalog

### 2.1 `ChatInterface.tsx`
- **Location**: `src/components/ChatInterface.tsx` (973 lines)
- **Role**: Primary client-side application orchestrator for student interactions.
- **Key States**:
  - `messages`: Array of `ChatMessage` objects stored in `localStorage`.
  - `isLoading`: Boolean disabling submit button during stream processing.
  - `activeAssistantId`: ID of the message currently receiving token chunks.
  - `queueInfo`: Virtual waiting queue state (`position`, `estimated_seconds`).
  - `isFeedbackModalOpen`: Toggles the integrated session feedback dialog.
- **Core Sub-sections**:
  - **Apple-inspired Hero View**: Displayed when `messages.length === 0`. Centers the brand pill, title, auto-resizing prompt box, and frequent normative suggestion chips.
  - **Conversation Thread**: Displayed when `messages.length > 0`. Renders user message bubbles, assistant cards with markdown, citation chips, and agent reasoning traces.
  - **Docked Footer**: Sticky prompt box pinned to the bottom of the viewport during an active conversation.
  - **1-Click Retry Action**: Conditional button rendered when an assistant response contains overload indicators (`reintenta` or `volumen muy alto`), allowing students to re-submit without typing.

### 2.2 `CitationBadge.tsx`
- **Location**: `src/components/CitationBadge.tsx` (141 lines)
- **Role**: Renders institutional legal citations (Acuerdos, Resoluciones, Estatutos) as interactive chips.
- **Props**:
  ```typescript
  interface Citation {
    title: string;          // Document title (e.g. "Acuerdo 028 de 2017")
    resolution?: string;    // Resolution identifier
    article?: string;       // Normative article (e.g. "Artículo 12")
    source_type?: string;   // Category: "acuerdo" | "resolucion"
    excerpt: string;        // Verbatim legal text excerpt
    pdf_url?: string;       // Direct link to official PDF
    document_id?: number;   // Backend document ID for route resolution
  }
  ```
- **UX Features**:
  - Pill trigger displaying document title and article number with hover effects.
  - Quick-action external link icon navigating directly to the official University PDF.
  - Click-to-open modal dialog rendered via React Portal (`createPortal(modal, document.body)`) to escape parent CSS stacking contexts and overflow clipping, providing full verified normative context, metadata, and a scrollable excerpt box.

### 2.3 `MoltenMetal.tsx` (`BackgroundWebGL`)
- **Location**: `src/components/MoltenMetal.tsx` (411 lines)
- **Role**: Fullscreen GPU-accelerated WebGL2 fluid mesh canvas using `ogl`.
- **Props & Configuration**:
  ```typescript
  export interface MoltenMetalProps {
    color1?: string;             // Primary palette hex (e.g. "#D4A017")
    color2?: string;             // Secondary palette hex
    color3?: string;             // Tertiary highlight hex
    speed?: number;              // Simulation velocity (default: 0.8)
    scale?: number;              // Noise frequency scale (default: 2.5)
    swirl?: number;              // Fluid rotation intensity
    glow?: number;               // Specular core glow
    colorMode?: "molten" | "ember" | "frost" | string;
    mouseInteraction?: boolean;  // Enables cursor velocity tracking
    mouseStrength?: number;      // Influence factor of cursor movement
  }
  ```
- **Performance Guards**: Caps `devicePixelRatio` at `2.0` and destroys the WebGL context on unmount via `WEBGL_lose_context`.

### 2.4 `AdminSidebar.tsx`
- **Location**: `src/components/admin/AdminSidebar.tsx` (394 lines)
- **Role**: Responsive navigation bar and drawer for the `/admin` portal.
- **Navigation Tabs**:
  - `analytics`: Performance KPIs, token throughput, and query analytics.
  - `triage`: Institutional email inbox and pending manual reviews.
  - `knowledge`: Normative documents inventory and vector chunk browser.
  - `settings`: System guardrails, relevance thresholds, and IP filters.
  - `feedback`: Student session ratings, feedback transcripts, and dispositions.
- **Real-Time Badges**: Queries `getAdminStats()` to show live counts on pending emails (`pending_emails`), total documents, and unread feedback.
- **Drawer Behavior**: Automatically collapses to a backdrop slide-over sheet on screens narrower than `1024px` (`lg` breakpoint).

### 2.5 Admin CRM Modules Catalog

#### `AnalyticsDashboardModule.tsx` (1,007 lines)
- Visualizes system health and student query patterns using `recharts`.
- Key views: Total query volume area charts, hourly traffic distributions, response latency percentiles (P50/P90/P99), top cited normative resolutions, and student sentiment charts.

#### `EmailTriageModule.tsx` (1,320 lines)
- Two-pane management interface for university emails sent to `canigraduateud@gmail.com`.
- Left pane: Filterable email list with status indicators (`pending`, `ingested`, `discarded`).
- Right pane: Rich message viewer, attachment preview, and markdown extractor for one-click ingestion into the Neon pgvector database.
- Fires `onDataChanged={fetchStats}` to refresh sidebar counters.

#### `KnowledgeBaseModule.tsx` (1,192 lines)
- Master catalog of all ingested normative documents.
- Includes a vector chunk inspector displaying chunk ID, token count, parent document reference, and vector similarity metrics.
- Features an interactive Semantic Probe allowing administrators to run test queries against the live vector index.
- Houses the `DocumentUploadModal`.

#### `SessionFeedbackModule.tsx` (510 lines)
- Quality control interface reviewing feedback submitted by students through `ChatInterface`.
- Filters records by star rating (1–5), submission timestamp, and category (`sugerencia`, `informacion_imprecisa`, `error_tecnico`, `general`).
- Displays full conversation transcripts linked to the session UUID.

#### `SettingsGuardrailsModule.tsx` (311 lines)
- Autonomous ingestion toggle: enables or disables automated document indexing.
- Relevance score slider: sets cosine similarity cutoffs for RAG retrieval.
- Safety filters: blacklisted keywords, forbidden prompt regexes, and IP penalty lists.

### 2.6 Integrated Modals & UI Primitives

#### `DocumentUploadModal` (inside `KnowledgeBaseModule.tsx`)
- Triggered by "Cargar Documento" or "Redactar en Markdown" buttons.
- Dual Mode:
  - **File Upload Tab**: Accepts `.pdf`, `.docx`, `.txt` files with metadata fields (Title, Resolution Number, Effective Date). Submits as `multipart/form-data`.
  - **Markdown Tab**: Direct text editor for pasting official normative resolutions in markdown syntax.

#### `FeedbackModal` (inside `ChatInterface.tsx`)
- Triggered by the "Feedback" button in the chat header or assistant message cards.
- Star Rating: 1 to 5 clickable stars.
- Category Selector: `sugerencia` | `informacion_imprecisa` | `error_tecnico` | `general`.
- Transcript Checkbox: Automatically includes recent messages from the session for forensic triage.
- Dual Delivery: Submits to `/api/v1/feedback` via REST API, while providing direct `mailto:` and `mail.google.com` fallback links.

#### `PixelDotsLoader` (inside `ui/agent-trace.tsx`)
- 3x3 pixel dot matrix loader animating on a 90ms staggered delay wave.
- Used during active LLM token generation and agent thinking phases.
- Minimal CPU footprint with CSS-only `@keyframes agent-pixel-on`.

#### `PromptInputBox` (inside `ui/ai-prompt-box.tsx`)
- Auto-expanding textarea handling multi-line queries.
- Keyboard bindings: `Enter` submits query, `Shift + Enter` inserts a newline.
- Responsive action buttons with dynamic send/loading spinner states.

---

## 3. Styling, Design Tokens & Themes

The application implements a tailored dual-personality design system via Tailwind CSS:

```
+-------------------------------------------------------------------------------+
|                            Dual-Personality Styling                           |
|                                                                               |
|   PUBLIC STUDENT VIEW (app/page.tsx)      ADMIN CRM PORTAL (app/admin/*)      |
|   ----------------------------------      ------------------------------      |
|   • Luxury Dark Aesthetic                 • Clean High-Density Light Palette  |
|   • Background: zinc-950 / Black          • Background: #FAF8F5 (Warm Canvas) |
|   • Fluid WebGL Canvas (ogl shaders)      • Cards: Solid White / Stone-200    |
|   • Borders: border-white/[0.08]          • Borders: border-stone-200/80      |
|   • Accents: Amber-400 / Amber-500        • Accents: Orange-600 / Stone-900   |
|   • Glassmorphism: backdrop-blur-xl       • Crisp, high-contrast tables       |
+-------------------------------------------------------------------------------+
```

### 3.1 Tailwind Configuration (`tailwind.config.js`)

The project extends the default Tailwind theme with Universidad Distrital institutional colors and custom shadow tokens:

```javascript
module.exports = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ud: {
          red: "#8B1E1E",       // Official UD Institutional Red
          darkred: "#5A1111",   // Dark Red Header Accent
          gold: "#D4A017",      // Institutional Gold
          navy: "#0F1E36",      // Deep Institutional Navy
          blue: "#1E3A8A",      // Accent Blue
        },
      },
      boxShadow: {
        xs: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
      },
    },
  },
};
```

### 3.2 Core Stylesheet (`src/app/globals.css`)

The stylesheet defines theme custom properties and Webkit dark scrollbars:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 0%;
    --foreground: 0 0% 98%;
    --card: 0 0% 7%;
    --card-foreground: 0 0% 98%;
    --popover: 0 0% 7%;
    --popover-foreground: 0 0% 98%;
    --primary: 38 92% 50%;
    --primary-foreground: 0 0% 100%;
    --secondary: 0 0% 14%;
    --secondary-foreground: 0 0% 98%;
    --muted: 0 0% 14%;
    --muted-foreground: 0 0% 65%;
    --accent: 0 0% 14%;
    --accent-foreground: 0 0% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 0 0% 98%;
    --border: 0 0% 18%;
    --input: 0 0% 18%;
    --ring: 38 92% 50%;
  }

  body {
    @apply bg-black text-foreground antialiased;
    font-feature-settings: "rlig" 1, "calt" 1;
  }
}

/* Custom dark scrollbars */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 9999px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}
```

---

## 4. WebGL MoltenMetal Fluid Background Integration

The component `src/components/MoltenMetal.tsx` renders a dynamic fluid shader using the lightweight `ogl` WebGL library.

### 4.1 Shader Architecture

- **Vertex Shader**: Computes a full-screen triangle quad covering coordinates `vec4(position, 0.0, 1.0)`.
- **Fragment Shader (`#version 300 es`)**:
  - Implements multi-octave 3D simplex noise with domain warping (`swirl` and `fold`).
  - Evaluates distance fields for organic molten surface waves.
  - Dynamically blends three color vectors (`uColor1`, `uColor2`, `uColor3`) based on fragment height and temperature coordinates.
  - Applies subtle analog film grain (`uGrainIntensity`) to eliminate banding on 8-bit displays.

### 4.2 Mouse Interaction & Physics Smoothing

Cursor coordinates are tracked via `pointermove` and smoothed using linear interpolation (lerp) to avoid jarring shader transitions:

```typescript
// Lerp smoothing loop inside requestAnimationFrame
mouse.current.targetX = e.clientX / window.innerWidth;
mouse.current.targetY = 1.0 - e.clientY / window.innerHeight;

// Frame update:
mouse.current.x += (mouse.current.targetX - mouse.current.x) * 0.05;
mouse.current.y += (mouse.current.targetY - mouse.current.y) * 0.05;
program.uniforms.uMouse.value = [mouse.current.x, mouse.current.y];
```

### 4.3 Lifecycle & Memory Safeguards

1. **Resolution Throttling**: Responds to `window.resize` events by updating canvas dimensions and shader uniforms with `Math.min(window.devicePixelRatio, 2.0)`.
2. **Context Cleanup**: On React unmount, the animation frame loop is cancelled, event listeners are purged, and the WebGL context is explicitly released:
   ```typescript
   gl.getExtension("WEBGL_lose_context")?.loseContext();
   ```

---

## 5. Accessibility & UI Guidelines

The application strictly adheres to WCAG 2.1 AA accessibility standards:

### 5.1 Semantic DOM Elements
- Pages are structured with top-level landmark elements: `<header>`, `<main>`, `<footer>`, `<aside>`, and `<nav>`.
- Headings follow strict hierarchical order (`<h1>` for title, `<h2>` for sections, `<h3>` for cards).

### 5.2 Dynamic Live Regions (`aria-live`)
- Streaming assistant responses utilize `aria-live="polite"` and `aria-atomic="false"`, ensuring screen readers announce progressive answer chunks without overwhelming speech synthesizers.
- Virtual queue position announcements (`En cola: #N de la fila`) declare `role="status"` and `aria-live="polite"`.

### 5.3 Keyboard Navigation & Dialog Focus Trapping
- All interactive buttons and citation chips feature visible focus rings (`focus-visible:ring-2 focus-visible:ring-amber-400`).
- Modals implemented via `@radix-ui/react-dialog` automatically trap keyboard focus, bind `Escape` to close, and restore focus to the triggering element upon dismissal.

### 5.4 Contrast Ratios
- Student view body text (`neutral-200`) provides a contrast ratio exceeding **12:1** against the `zinc-950` dark background.
- Normative citation badges use high-contrast amber foregrounds (`amber-300`, `#FCD34D`) over low-opacity badge containers (`amber-500/10`).
