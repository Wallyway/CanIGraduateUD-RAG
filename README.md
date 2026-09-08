# 🎓 Can I Graduate UD? (CanIGraduateUD-RAG)

[![Next.js](https://img.shields.io/badge/Next.js-14.2.5-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-18.3.1-blue?style=flat-square&logo=react)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![ChromaDB](https://img.shields.io/badge/VectorStore-ChromaDB-FF6F00?style=flat-square)](https://www.trychroma.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38B2AC?style=flat-square&logo=tailwind-css)](https://tailwindcss.com/)

> **Sistema Agéntico RAG y Plataforma CRM de Gobernanza Normativa** para resolver dudas sobre requisitos, opciones y trámites de grado en el programa de **Ingeniería de Sistemas de la Universidad Distrital Francisco José de Caldas**.

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
│ • Clickable Citation Badges  │                         │ • 4. Guardrails & Autogestión│
│ • Visor PDF Nueva Pestaña    │                         │ • 5. Simulador de Correos    │
└──────────────┬───────────────┘                         └──────────────┬───────────────┘
               │                                                        │
               ▼                                                        ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                BACKEND API (FastAPI)                                  │
├───────────────────────────────────────────────────────────────────────────────────────┤
│ • RAG Engine (OpenRouter / Gemini 2.0 Flash / OpenAI)                                 │
│ • Markdown Converter & Derogation Clause Detector (pypdf)                             │
│ • Triage Agent & IMAP Mailbox Poller (canigraduateud@gmail.com)                      │
│ • Analytics Aggregator & Student Query Logger                                         │
│ • Strict Institutional Guardrails & Derogation Conflict Detector                     │
└───────────────────────┬───────────────────────────────────────┬───────────────────────┘
                        ▼                                       ▼
       ┌─────────────────────────────────┐    ┌──────────────────────────────────┐
       │     ChromaDB (Vector Store)     │    │   SQLite (Metadatos & Logs)      │
       │  • Fragmentación semántica      │    │  • DocumentItem (Linaje & Docs)  │
       │  • Eliminación por derogación   │    │  • EmailNotice (Triage)          │
       │  • Búsqueda por similitud       │    │  • StudentQueryLog (KPIs & Gaps) │
       │  • Metadatos de artículos & PDF │    │  • SystemSetting (Guardrails)    │
       └─────────────────────────────────┘    └──────────────────────────────────┘
```

---

## 🚀 Módulos y Funcionalidades

### 1. Experiencia del Estudiante (`/`)
* **Diseño Apple Minimalist**: Tipografía SF Pro Display, fondo procedimental WebGL **`MoltenMetal`** con flujo de magma incandescente interactivo con el mouse (`ogl`), y tarjetas de cristal esmerilado (`backdrop-blur-2xl`).
* **Caja de Entrada Enriquecida (`PromptInputBox`)**: Atajos de teclado, selector de modos, carga visual de archivos y píldoras de preguntas sugeridas.
* **Streaming Fluido de Tokens**: Respuestas transmitidas por Server-Sent Events (SSE) con animación suave de aparición palabra por palabra (`word-fade`) mediante curvas de aceleración `cubic-bezier`.
* **Trazabilidad Agéntica (`ThinkingState` / `PixelDotsLoader`)**: Visualización interactiva de los pasos de búsqueda en ChromaDB, acuerdos analizados y razonamiento normativo, que colapsa de forma limpia en *"Consultó normativa durante Xs"*.
* **Citaciones Oficiales Interactivas (`CitationBadge`)**:
  * Botón directo con ícono `ExternalLink` que abre el documento o PDF oficial en una **nueva pestaña** (`target="_blank"`).
  * Modal emergente con el fragmento normativo exacto, artículo y fecha de emisión.
* **Guardrail Anti-Alucinación**: Si la pregunta no está contemplada en la normativa oficial cargada, el asistente lo declara explícitamente y orienta al estudiante hacia la dependencia encargada (Coordinación de Ingeniería de Sistemas o Secretaría de Facultad).

---

### 2. CRM Administrativo (`/admin`)
Inspirado en la disposición de barra lateral fija y visibilidad de datos tipo **Autumn** y **Shadcn/ui**, estructurado con la paleta cálida **Claude Light** (`#FAF8F5`, `#FFFFFF`, acentos terracota `#C2410C` y ámbar `#D97706`):

#### A. Bandeja de Triage e Ingestión de Correos (`EmailTriageModule`)
* Conexión continua con el buzón institucional vía IMAP (`canigraduateud@gmail.com`) y soporte para Webhooks HTTP desde Microsoft 365 Power Automate.
* **Evaluación Agéntica con LLM**: Puntaje de relevancia (0–100%), justificación del veredicto y propuesta de metadatos.
* **Editor Inline de Metadatos**: Permite al administrador ajustar el título propuesto, número de resolución, fecha de vigencia y resumen curado antes de incorporar el comunicado al RAG.
* **Acciones en Lote (Batch)**: Checkboxes para aprobar o descartar múltiples comunicados en un solo clic.

#### B. Base de Conocimiento y Linaje Normativo (`KnowledgeBaseModule`)
* Inventario normativo clasificado en tres estados de vigencia: `VIGENTE`, `MODIFICADO` y `DEROGADO`.
* **Árbol de Linaje Normativo**: Vinculación relacional para saber qué acuerdo sustituye o modifica a otro (`supersedes_id`).
* **Conversión PDF a Markdown Estructurado**: Procesador abierto con `pypdf` que limpia encabezados/pies de página, detecta cláusulas de derogación (*"deroga el acuerdo...", "modifica el artículo..."*) y genera Markdown limpio optimizado para embeddings.
* **Probador Semántico en Tiempo Real**: Permite al administrador ingresar una consulta de prueba ("requisitos pasantía") y examinar al instante la distancia matemática y los fragmentos devueltos por ChromaDB.
* **Purgado Inmediato de Derogaciones**: Al marcar una resolución como derogada, sus fragmentos se eliminan automáticamente de ChromaDB para impedir citas a normas sin vigencia.

#### C. Analítica de Estudiantes (`AnalyticsDashboardModule`)
* **Hero Card con Gráfico Interactivo de Área (Estilo Shadcn/ui & Dribbble)**:
  * Curvas con gradientes SVG suaves y tooltips enriquecidos.
  * **4 Tarjetas Selectoras de KPIs Conectadas**:
    1. *Consultas Estudiantes* (volumen total y porcentaje de crecimiento).
    2. *Tasa de Cobertura RAG* (% de consultas con respaldo oficial).
    3. *Tasa de Brechas* (% de dudas que requieren nuevas normas).
    4. *Tiempo Promedio de Respuesta* (latencia media en segundos).
  * Al hacer clic en cualquier tarjeta, el gráfico superior conmuta fluidamente la serie temporal y la escala.
* **Workflow Breakdown (Distribución Temática)**: Desglose porcentual por categorías (Modalidades, Paz y Salvos, Pasantías, Inglés B2, Plan de Estudios) con barras de progreso e indicadores de estado (*Estable*, *Moderado*, *Brechas*).
* **System Health (Salud del Sistema & Guardrails)**:
  * Métrica global de operatividad (87% - Óptimo).
  * Diálogo modal interactivo con **barras segmentadas por bloques** (Success rate 98.1%, Gap rate 1.9%, Avg runtime 1.4s).
* **Ranking de Preguntas Frecuentes Reales**: Dudas recurrentes de estudiantes con la fuente normativa citada para responderlas.
* **Monitor de Brechas de Conocimiento (*Knowledge Gaps*)**: Registro proactivo de preguntas con baja confianza o sin resolución asociada para guiar la carga de nuevos documentos.

#### D. Guardrails & Configuración de Autogestión (`SettingsGuardrailsModule`)
* **Interruptor Maestro de Autogestión**: Permite activar o pausar la autoindexación directa de correos entrantes.
* **Slider de Umbral de Confianza**: Calibración del porcentaje mínimo de certeza requerido al LLM (por defecto 85%).
* **Filtro Estricto de Dominio**: Bloquea correos no provenientes del dominio oficial `@udistrital.edu.co`.
* **Detector de Conflictos Normativos**: Detiene la autoindexación y solicita intervención humana si el correo contiene términos derogatorios.

---

### 3. Simulador de Correos Institucionales (`/admin/simulator`)
* Herramienta para simular el envío de comunicados oficiales con remitente, asunto, cuerpo y adjuntos.
* Plantillas preconfiguradas:
  * Convocatoria de Modalidades de Grado 2026-1 (Ingeniería de Sistemas).
  * Cronograma de Paz y Salvos y Ceremonia de Grados.
  * Comunicado no relevante (Bienestar / Torneo de Ajedrez) para verificar el descarte del LLM.

---

## 📚 Normativa Oficial Preindexada

El sistema incluye en `backend/data/seed_documents/` las resoluciones y procedimientos base de la Universidad Distrital:

1. **Acuerdo No. 027 de 1993 (CSU)**: Estatuto Estudiantil de la Universidad Distrital (requisitos de grado, promedios y permanencia).
2. **Acuerdo No. 038 de 2015 (Consejo de Facultad de Ingeniería)**: Reglamentación de las 8 modalidades de grado en Ingeniería (Pasantía Institucional, Monografía, Materias de Posgrado, Producción Intelectual, Creación de Empresa, Cursos de Actualización, Preparatorios, Distinción Saber Pro).
3. **Acuerdo No. 004 de 2021 (Consejo Académico)**: Requisito de suficiencia en segunda lengua (Nivel B2 certificado o convalidado por el ILUD).
4. **Procedimiento de Paz y Salvos y Grados Cóndor**: Requisitos de biblioteca (RIUD), laboratorios, carnetización, derechos pecuniarios de grado y recepción de carpetas.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnologías |
| :--- | :--- |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Framer Motion, OGL (WebGL), Recharts 3, Radix UI, Lucide Icons |
| **Backend** | FastAPI, Python 3.11, Pydantic v2, Uvicorn |
| **Bases de Datos** | ChromaDB (Vector Store persistente), SQLite con SQLAlchemy ORM |
| **Modelos & LLM** | OpenRouter (Google Gemini 2.0 Flash / 1.5 Flash), OpenAI API spec |
| **Procesamiento PDF** | PyPDF, MarkdownConverter con regex normativo y extracción de artículos |
| **Email & Mensajería** | IMAP (SSL puerto 993), SSE (Server-Sent Events) |
| **DevOps & Contenedores** | Docker, Docker Compose, Mise (`.mise.toml`), pnpm |

---

## 📦 Instalación y Despliegue

### Requisitos Previos
* Docker y Docker Compose instalados, o
* Python 3.11+ y Node.js 20+ con `pnpm`.

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
   * **Chat de Estudiantes**: [http://localhost:3000](http://localhost:3000)
   * **CRM de Administración**: [http://localhost:3000/admin](http://localhost:3000/admin)
     * **Usuario**: `admin_ud`
     * **Contraseña**: `graduacion_sistemas_2026!`
   * **Documentación OpenAPI (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Opción 2: Desarrollo Local

#### 1. Backend (FastAPI):
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Indexar la normativa semilla en ChromaDB:
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

* **URL Administrador**: `http://localhost:3000/admin`
* **Usuario**: `admin_ud`
* **Contraseña**: `graduacion_sistemas_2026!`
* **Buzón IMAP Monitoreado**: `canigraduateud@gmail.com`

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
│   │   │   ├── models.py          # Modelos SQLAlchemy (Documentos, Triage, Logs)
│   │   │   └── session.py         # Conexión SQLite y migraciones seguras
│   │   ├── scripts/
│   │   │   └── seed_db.py         # Semillero e indexador de normativas UD
│   │   └── services/
│   │       ├── document_processor.py # Fragmentación de artículos
│   │       ├── email_service.py      # Lector IMAP
│   │       ├── markdown_converter.py # Conversor PDF a MD con cláusulas
│   │       ├── rag_service.py        # Orquestador RAG y citaciones oficiales
│   │       ├── triage_service.py     # Agente evaluador de correos con guardrails
│   │       └── vector_store.py       # Driver ChromaDB
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
