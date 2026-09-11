# 🎓 Can I Graduate UD? (CanIGraduateUD-RAG)

[![Next.js](https://img.shields.io/badge/Next.js-14.2.5-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-18.3.1-blue?style=flat-square&logo=react)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![Neon pgvector](https://img.shields.io/badge/VectorStore-Neon%20pgvector-00E599?style=flat-square&logo=postgresql)](https://neon.tech/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![Upstash Redis](https://img.shields.io/badge/Cache-Upstash%20Redis-00E599?style=flat-square&logo=redis)](https://upstash.com/)
[![Production](https://img.shields.io/badge/Website-canigraduateud.site-black?style=flat-square&logo=vercel)](https://www.canigraduateud.site)

> 🌐 **Despliegue en Producción**: [https://www.canigraduateud.site](https://www.canigraduateud.site)
>
> **Sistema Agéntico RAG de Alta Disponibilidad y Plataforma CRM de Gobernanza Normativa** para resolver dudas sobre requisitos, opciones y trámites de grado en el programa de **Ingeniería de Sistemas de la Universidad Distrital Francisco José de Caldas**.

El sistema se fundamenta de forma estricta y verificable en acuerdos, estatutos y comunicados oficiales vigentes de la universidad, eliminando alucinaciones mediante citas explícitas a artículos normativos y proporcionando a los coordinadores académicos un CRM completo para supervisar correos entrantes, administrar el linaje normativo y monitorear las consultas de los estudiantes.

---

## 📸 Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CAN I GRADUATE UD? ARCHITECTURE                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
┌──────────────────────────────┐                         ┌──────────────────────────────┐
│    VISTA ESTUDIANTE ( / )    │                         │       CRM ADMIN ( /admin )   │
│   (Apple Minimalist Theme)   │                         │     (Claude / Autumn Theme)  │
├──────────────────────────────┤                         ├──────────────────────────────┤
│ • WebGL MoltenMetal Embers   │                         │ • Split-View Sidebar Layout  │
│ • Rich PromptInputBox        │                         │ • 1. Triage & Ingestión Mail │
│ • SSE Stream & Word Fade-In  │                         │ • 2. Base de Conocimiento MD │
│ • Agent Trace & PixelDots    │                         │ • 3. Analítica (Airlytics)   │
│ • React Portal Citations     │                         │ • 4. Guardrails & Autogestión│
│ • Baneo 24h & /ban-status    │                         │ • 5. Simulador de Correos    │
│ • Vercel Analytics & WebGL   │                         │ • Visor PDF en Nueva Pestaña │
└──────────────┬───────────────┘                         └──────────────┬───────────────┘
               │                                                        │
               ▼                                                        ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                BACKEND API (FastAPI)                                  │
├───────────────────────────────────────────────────────────────────────────────────────┤
│ • RAG Engine Stateless (OpenRouter Multi-Model / Llama 3.1 8B / Gemini 2.0 Flash)    │
│ • Virtual Queue Concurrency (Semáforo 150 permisos, cola FIFO 100 y keepalive : ping) │
│ • Zero-Token Security Gates (Baneo 24h /ban-status, Rate Limiter, 3-Strikes Anti-Abuse)│
│ • Conversor PDF a Markdown & Extracción de Cláusulas Derogatorias (pypdf)            │
│ • Triage Agent & IMAP Mailbox Poller (canigraduateud@gmail.com)                      │
│ • Logging de Consultas & Analytics Aggregator (StudentQueryLog, SessionFeedback)     │
└───────────────────────┬───────────────────────────────────────┬───────────────────────┘
                        ▼                                       ▼
       ┌─────────────────────────────────┐    ┌──────────────────────────────────┐
       │   Neon PostgreSQL + pgvector    │    │      Caché Híbrida & Storage     │
       │  • pgvector HNSW cosine (1536d) │    │  • Upstash Redis + RAM Fallback  │
       │  • DocumentChunk (100% stateless)│   │  • Layer 1 Exacto (SHA-256)      │
       │  • Cascada ACID en derogación   │    │  • Layer 2 Semántico (>= 0.95)   │
       │  • 7 Modelos SQLAlchemy ORM     │    │  • QueuePool (30 base + 50 over) │
       │  • SQLite fallback para pruebas │    │  • SQLite dev fallback local     │
       └─────────────────────────────────┘    └──────────────────────────────────┘
```

---

## 🚀 Módulos y Funcionalidades

### 1. Experiencia del Estudiante (`/`)

- **Diseño Apple Minimalist**: Tipografía SF Pro Display, fondo procedimental WebGL **`MoltenMetal`** con flujo de magma incandescente interactivo con el mouse (`ogl`), y tarjetas de cristal esmerilado (`backdrop-blur-2xl`).
- **Caja de Entrada Enriquecida (`PromptInputBox`)**: Atajos de teclado, selector de modos, carga visual de archivos y píldoras de preguntas sugeridas.
- **Streaming Fluido de Tokens**: Respuestas transmitidas por Server-Sent Events (SSE) con animación suave de aparición palabra por palabra (`word-fade`) mediante curvas de aceleración `cubic-bezier`.
- **Trazabilidad Agéntica (`ThinkingState` / `PixelDotsLoader`)**: Visualización interactiva de los pasos de búsqueda vectorial en Neon pgvector, acuerdos analizados y razonamiento normativo, que colapsa de forma limpia en _"Consultó normativa durante Xs"_.
- **Citaciones Oficiales Interactivas (`CitationBadge`)**:
  - Renderizadas mediante **React Portal** (`createPortal`) montado en `document.body` para garantizar aislamiento visual total, previniendo recortes por `overflow-hidden` o colisiones de apilamiento `z-index`.
  - Botón directo con ícono `ExternalLink` que abre el documento o PDF oficial en una **nueva pestaña** (`target="_blank"`).
  - Modal emergente con el fragmento normativo exacto, artículo y fecha de emisión.
- **Defensa Multi-Factor contra Abuso (Baneo 24h & `/ban-status`)**: Detección de inyecciones o abusos no académicos con regla de 3 strikes que aplica un baneo de 24 horas multi-factor (IP, Subnet `/24`, MAC y Device ID), sincronizado en tiempo real entre `localStorage` (`ud_banned_until`) y el endpoint `/api/v1/chat/ban-status`.
- **Telemetría y Rendimiento Web (Vercel Analytics & Next.js 14)**: Integración nativa de `@vercel/analytics/next` en el `RootLayout` para monitorear rendimiento y Core Web Vitals.
- **Guardrail Anti-Alucinación**: Si la pregunta no está contemplada en la normativa oficial cargada, el asistente lo declara explícitamente y orienta al estudiante hacia la dependencia encargada (Coordinación de Ingeniería de Sistemas o Secretaría de Facultad).

---

### 2. CRM Administrativo (`/admin`)

Inspirado en la disposición de barra lateral fija y visibilidad de datos tipo **Autumn** y **Shadcn/ui**, estructurado con la paleta cálida **Claude Light** (`#FAF8F5`, `#FFFFFF`, acentos terracota `#C2410C` y ámbar `#D97706`):

#### A. Bandeja de Triage e Ingestión de Correos (`EmailTriageModule`)

- Conexión continua con el buzón institucional vía IMAP (`canigraduateud@gmail.com`) y soporte para Webhooks HTTP desde Microsoft 365 Power Automate.
- **Evaluación Agéntica con LLM**: Puntaje de relevancia (0–100%), justificación del veredicto y propuesta de metadatos.
- **Editor Inline de Metadatos**: Permite al administrador ajustar el título propuesto, número de resolución, fecha de vigencia y resumen curado antes de incorporar el comunicado al RAG.
- **Acciones en Lote (Batch)**: Checkboxes para aprobar o descartar múltiples comunicados en un solo clic con vectorización en Neon pgvector.

#### B. Base de Conocimiento y Linaje Normativo (`KnowledgeBaseModule`)

- Inventario normativo clasificado en tres estados de vigencia: `VIGENTE`, `MODIFICADO` y `DEROGADO`.
- **Árbol de Linaje Normativo**: Vinculación relacional para saber qué acuerdo sustituye o modifica a otro (`supersedes_id`).
- **Conversión PDF a Markdown Estructurado**: Procesador abierto con `pypdf` que limpia encabezados/pies de página, detecta cláusulas de derogación (_"deroga el acuerdo...", "modifica el artículo..."_) y genera Markdown limpio optimizado para embeddings.
- **Probador Semántico en Tiempo Real**: Permite al administrador ingresar una consulta de prueba ("requisitos pasantía") y examinar al instante la distancia matemática y los fragmentos devueltos por Neon pgvector.
- **Purgado Inmediato de Derogaciones**: Al marcar una resolución como derogada, sus fragmentos se eliminan automáticamente de Neon pgvector mediante cascada transaccional ACID (`DocumentChunk`) para impedir citas a normas sin vigencia.

#### C. Analítica de Estudiantes (`AnalyticsDashboardModule`)

- **Hero Card con Gráfico Interactivo de Área (Estilo Shadcn/ui & Dribbble)**:
  - Curvas con gradientes SVG suaves y tooltips enriquecidos.
  - **4 Tarjetas Selectoras de KPIs Conectadas**:
    1. _Consultas Estudiantes_ (volumen total y porcentaje de crecimiento).
    2. _Tasa de Cobertura RAG_ (% de consultas con respaldo oficial).
    3. _Tasa de Brechas_ (% de dudas que requieren nuevas normas).
    4. _Tiempo Promedio de Respuesta_ (latencia media en segundos).
  - Al hacer clic en cualquier tarjeta, el gráfico superior conmuta fluidamente la serie temporal y la escala.
- **Workflow Breakdown (Distribución Temática)**: Desglose porcentual por categorías (Modalidades, Paz y Salvos, Pasantías, Inglés B2, Plan de Estudios) con barras de progreso e indicadores de estado (_Estable_, _Moderado_, _Brechas_).
- **System Health (Salud del Sistema & Guardrails)**:
  - Métrica global de operatividad (87% - Óptimo).
  - Diálogo modal interactivo con **barras segmentadas por bloques** (Success rate 98.1%, Gap rate 1.9%, Avg runtime 1.4s).
- **Ranking de Preguntas Frecuentes Reales**: Dudas recurrentes de estudiantes con la fuente normativa citada para responderlas.
- **Monitor de Brechas de Conocimiento (_Knowledge Gaps_)**: Registro proactivo de preguntas con baja confianza o sin resolución asociada para guiar la carga de nuevos documentos.

#### D. Guardrails & Configuración de Autogestión (`SettingsGuardrailsModule`)

- **Interruptor Maestro de Autogestión**: Permite activar o pausar la autoindexación directa de correos entrantes.
- **Slider de Umbral de Confianza**: Calibración del porcentaje mínimo de certeza requerido al LLM (por defecto 85%).
- **Filtro Estricto de Dominio**: Bloquea correos no provenientes del dominio oficial `@udistrital.edu.co`.
- **Detector de Conflictos Normativos**: Detiene la autoindexación y solicita intervención humana si el correo contiene términos derogatorios.

---

### 3. Simulador de Correos Institucionales (`/admin/simulator`)

- Herramienta para simular el envío de comunicados oficiales con remitente, asunto, cuerpo y adjuntos.
- Plantillas preconfiguradas:
  - Convocatoria de Modalidades de Grado 2026-1 (Ingeniería de Sistemas).
  - Cronograma de Paz y Salvos y Ceremonia de Grados.
  - Comunicado no relevante (Bienestar / Torneo de Ajedrez) para verificar el descarte del LLM.

---

## 📚 Normativa Oficial Preindexada

El sistema incluye en `backend/data/seed_documents/` las resoluciones y procedimientos base de la Universidad Distrital:

1. **Acuerdo No. 027 de 1993 (CSU)**: Estatuto Estudiantil de la Universidad Distrital (requisitos de grado, promedios y permanencia).
2. **Acuerdo No. 038 de 2015 (Consejo de Facultad de Ingeniería)**: Reglamentación de las 8 modalidades de grado en Ingeniería (Pasantía Institucional, Monografía, Materias de Posgrado, Producción Intelectual, Creación de Empresa, Cursos de Actualización, Preparatorios, Distinción Saber Pro).
3. **Acuerdo No. 004 de 2021 (Consejo Académico)**: Requisito de suficiencia en segunda lengua (Nivel B2 certificado o convalidado por el ILUD).
4. **Procedimiento de Paz y Salvos y Grados Cóndor**: Requisitos de biblioteca (RIUD), laboratorios, carnetización, derechos pecuniarios de grado y recepción de carpetas.

---

## 🛠️ Stack Tecnológico

| Capa                      | Tecnologías                                                                                                                 |
| :------------------------ | :-------------------------------------------------------------------------------------------------------------------------- |
| **Frontend**              | Next.js 14 (App Router), React 18 (React Portal `createPortal`), TypeScript, Tailwind CSS, Framer Motion, OGL (WebGL), Recharts 3, Radix UI, Lucide Icons, Vercel Analytics (`@vercel/analytics/next`) |
| **Backend**               | FastAPI 0.111+, Python 3.11, Pydantic v2, Uvicorn, SQLAlchemy 2.0+ (`QueuePool`), Virtual Queue Concurrency (150 slots)    |
| **Bases de Datos**        | Neon PostgreSQL 16 con extensión `pgvector` (`DocumentChunk` 1536-d HNSW), SQLite como fallback local de desarrollo         |
| **Caché Híbrida**         | Upstash Redis + Fallback en RAM thread-safe (Capa 1: SHA-256 exacto, Capa 2: Similitud Coseno semántica >= 0.95)          |
| **Modelos & LLM**         | OpenRouter Multi-Model con motor de resiliencia (Primario: `Llama 3.1 8B`; Fallbacks: `Llama 3.3 70B`, `Gemini 2.0 Flash`)   |
| **Seguridad & Gobernanza**| Guardrails pre-vuelo 0 tokens: Baneo 24h multi-factor con endpoint `/ban-status`, rate limit 10 req/min, regla de 3 strikes |
| **Procesamiento PDF**     | PyPDF, MarkdownConverter con regex normativo y extracción de artículos                                                      |
| **Email & Mensajería**    | IMAP (SSL puerto 993), SSE (Server-Sent Events) con heartbeat `: ping` cada 15s                                             |
| **DevOps & Contenedores** | Docker, Docker Compose, Mise (`.mise.toml`), pnpm                                                                           |

---

## 📦 Instalación y Despliegue

### Requisitos Previos

- Docker y Docker Compose instalados, o
- Python 3.11+ y Node.js 20+ con `pnpm`.

---

### Opción 1: Con Docker Compose (Recomendado)

1. **Clonar el repositorio**:

   ```bash
   git clone https://github.com/Wallyway/CanIGraduateUD-RAG.git
   cd CanIGraduateUD-RAG
   ```

2. **Configurar variables de entorno**:

   ```bash
   cp .env.example .env
   ```

   Edita `.env` y agrega tu clave de OpenRouter (o proveedor preferido):

   ```env
   OPENROUTER_API_KEY=tu_api_key_aqui
   OPENROUTER_MODEL=google/gemini-2.0-flash-001
   ```

3. **Compilar y levantar los contenedores**:

   ```bash
   docker compose up -d --build
   ```

4. **Acceder a la plataforma**:
   - **Chat de Estudiantes**: [http://localhost:3000](http://localhost:3000)
   - **CRM de Administración**: [http://localhost:3000/admin](http://localhost:3000/admin)
     - **Usuario**: `admin_ud`
     - **Contraseña**: `graduacion_sistemas_2026!`
   - **Documentación OpenAPI (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Opción 2: Desarrollo Local

#### 1. Backend (FastAPI):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Indexar la normativa semilla en la base de datos (PostgreSQL pgvector / SQLite fallback):
python -m app.scripts.seed_db

# Iniciar el servidor backend:
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend (Next.js):

```bash
cd frontend
pnpm install
pnpm dev
```

El frontend estará disponible en `http://localhost:3000`.

---

## 🔑 Credenciales y Accesos por Defecto

- **URL Administrador**: `http://localhost:3000/admin`
- **Usuario**: `admin_ud`
- **Contraseña**: `graduacion_sistemas_2026!`
- **Buzón IMAP Monitoreado**: `canigraduateud@gmail.com`

---

## 📂 Estructura del Proyecto

```
CanIGraduateUD-RAG/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── admin.py           # Endpoints de CRM, métricas y configuración
│   │   │   ├── auth.py            # Autenticación JWT de administrador
│   │   │   ├── chat.py            # Endpoint de streaming SSE y logging de dudas
│   │   │   ├── documents.py       # CRUD normativo, visor PDF y probador semántico
│   │   │   └── webhooks.py        # Receptor de comunicados M365
│   │   ├── core/
│   │   │   └── config.py          # Variables de entorno y ajustes
│   │   ├── db/
│   │   │   ├── models.py          # Modelos SQLAlchemy (7 tablas: Documentos, Chunks, Logs, Triage)
│   │   │   └── session.py         # Conexión QueuePool, PostgreSQL 16 y SQLite dev
│   │   ├── scripts/
│   │   │   └── seed_db.py         # Semillero e indexador de normativas UD
│   │   └── services/
│   │       ├── document_processor.py # Fragmentación de artículos
│   │       ├── email_service.py      # Lector IMAP
│   │       ├── markdown_converter.py # Conversor PDF a MD con cláusulas
│   │       ├── rag_service.py        # Orquestador RAG y citaciones oficiales
│   │       ├── triage_service.py     # Agente evaluador de correos con guardrails
│   │       └── vector_store.py       # Almacén vectorial Neon pgvector (DocumentChunk)
│   ├── data/
│   │   └── seed_documents/        # Resoluciones oficiales en Markdown
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── admin/
│   │   │   │   ├── documents/page.tsx # Vista de documentos
│   │   │   │   ├── login/page.tsx     # Inicio de sesión admin
│   │   │   │   ├── simulator/page.tsx # Simulador de correos
│   │   │   │   ├── layout.tsx         # Layout split-view con barra lateral
│   │   │   │   └── page.tsx           # Dashboard CRM modular
│   │   │   ├── layout.tsx             # Root layout
│   │   │   └── page.tsx               # Chat de estudiantes
│   │   ├── components/
│   │   │   ├── admin/
│   │   │   │   ├── AdminSidebar.tsx             # Barra lateral fija de navegación
│   │   │   │   ├── AnalyticsDashboardModule.tsx # Gráfico interactivo y salud
│   │   │   │   ├── EmailTriageModule.tsx        # Triage y editor de metadatos
│   │   │   │   ├── KnowledgeBaseModule.tsx      # Linaje, carga y probador RAG
│   │   │   │   └── SettingsGuardrailsModule.tsx # Guardrails de autogestión
│   │   │   ├── ui/
│   │   │   │   ├── agent-trace.tsx    # Trazas y PixelDotsLoader
│   │   │   │   └── ai-prompt-box.tsx  # Input de chat interactivo
│   │   │   ├── ChatInterface.tsx      # Interfaz principal de estudiante
│   │   │   ├── CitationBadge.tsx      # Citaciones con enlace a PDF en pestaña nueva
│   │   │   └── MoltenMetal.tsx        # Shader WebGL de brasas incandescentes
│   │   └── lib/
│   │       ├── api.ts                 # Cliente API REST y SSE
│   │       └── storage.ts             # Persistencia local
│   ├── Dockerfile
│   ├── package.json
│   └── tailwind.config.js
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 📄 Licencia

Este proyecto fue desarrollado con propósitos académicos y de optimización institucional para el Proyecto Curricular de **Ingeniería de Sistemas de la Universidad Distrital Francisco José de Caldas**. Distribuido bajo la Licencia MIT.
