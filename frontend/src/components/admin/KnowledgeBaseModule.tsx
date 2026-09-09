"use client";

import React, { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Database,
  UploadCloud,
  Search,
  FileText,
  Trash2,
  AlertOctagon,
  CheckCircle2,
  ExternalLink,
  GitCommit,
  GitBranch,
  RefreshCw,
  Sparkles,
  BookOpen,
  ArrowRight,
  CornerDownRight,
  ShieldAlert,
  Info,
  PenTool,
  Eye,
  FileCode,
  FileCheck,
  Camera
} from "lucide-react";
import {
  getDocuments,
  uploadDocument,
  createMarkdownDocument,
  deleteDocument,
  deprecateDocument,
  testSemanticSearch,
  getDocumentPdfUrl,
  getDocumentScanUrl
} from "@/lib/api";

export interface DocumentData {
  id: number;
  title: string;
  filename: string;
  file_type: string;
  source_type: string;
  resolution_number: string;
  effective_date: string;
  chunk_count: number;
  status: string;
  validity_status: "VIGENTE" | "MODIFICADO" | "DEROGADO";
  supersedes_id?: number | null;
  superseded_by_title?: string | null;
  has_markdown?: boolean;
  has_scan_image?: boolean;
  scan_url?: string | null;
  original_pdf_url?: string;
  created_at?: string;
}

export function KnowledgeBaseModule() {
  const [documents, setDocuments] = useState<DocumentData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [validityFilter, setValidityFilter] = useState<string>("ALL");

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadTab, setUploadTab] = useState<"file" | "markdown">("file");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadResolution, setUploadResolution] = useState("");
  const [uploadDate, setUploadDate] = useState("");
  const [supersedesDocId, setSupersedesDocId] = useState<string>("");
  const [markdownContent, setMarkdownContent] = useState("");
  const [uploadScanFile, setUploadScanFile] = useState<File | null>(null);
  const [scanPreviewUrl, setScanPreviewUrl] = useState<string | null>(null);
  const [previewMarkdown, setPreviewMarkdown] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  // Semantic search test state
  const [testQuery, setTestQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<any[]>([]);

  const fetchDocs = async () => {
    setIsLoading(true);
    try {
      const data = await getDocuments();
      setDocuments(data);
    } catch (e) {
      console.error("Error cargando documentos", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;

    setIsUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", uploadFile);
      if (uploadTitle) fd.append("title", uploadTitle);
      if (uploadResolution) fd.append("resolution_number", uploadResolution);
      if (uploadDate) fd.append("effective_date", uploadDate);
      if (supersedesDocId) fd.append("supersedes_id", supersedesDocId);

      const res = await uploadDocument(fd);
      alert(res.message || "Documento indexado con éxito.");
      setIsUploadOpen(false);
      setUploadFile(null);
      setUploadTitle("");
      setUploadResolution("");
      setUploadDate("");
      setSupersedesDocId("");
      fetchDocs();
    } catch (err: any) {
      alert("Error al subir documento: " + err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleCreateMarkdown = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!markdownContent.trim() || markdownContent.trim().length < 15) {
      alert("Por favor escribe o pega el contenido del acuerdo en Markdown (mínimo 15 caracteres).");
      return;
    }

    setIsUploading(true);
    try {
      const res = await createMarkdownDocument({
        title: uploadTitle.trim() || "Acuerdo Institucional UD",
        content: markdownContent.trim(),
        resolution_number: uploadResolution.trim() || undefined,
        effective_date: uploadDate || undefined,
        supersedes_id: supersedesDocId ? Number(supersedesDocId) : null,
        scan_file: uploadScanFile,
      });

      alert(res.message || "Acuerdo en Markdown indexado exitosamente en ChromaDB.");
      setIsUploadOpen(false);
      setMarkdownContent("");
      setUploadTitle("");
      setUploadResolution("");
      setUploadDate("");
      setSupersedesDocId("");
      setUploadScanFile(null);
      if (scanPreviewUrl) URL.revokeObjectURL(scanPreviewUrl);
      setScanPreviewUrl(null);
      setPreviewMarkdown(false);
      fetchDocs();
    } catch (err: any) {
      alert("Error al indexar acuerdo Markdown: " + err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadTemplate = () => {
    if (markdownContent.trim() && !confirm("¿Deseas reemplazar el contenido actual con la plantilla oficial UD?")) {
      return;
    }
    setMarkdownContent(`# UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS
## CONSEJO ACADÉMICO
### ACUERDO N° 000 DE 2026

"Por el cual se reglamenta el trabajo de grado y modalidades para los programas de pregrado de la Universidad Distrital Francisco José de Caldas"

EL CONSEJO ACADÉMICO DE LA UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS,
en uso de sus atribuciones legales y estatutarias, y

CONSIDERANDO:
Que el Estatuto Estudiantil reglamenta los requisitos para optar al título profesional.
Que se hace necesario actualizar las modalidades de trabajo de grado.

ACUERDA:

### CAPÍTULO I. DE LAS MODALIDADES DE TRABAJO DE GRADO

**Artículo 1. Modalidades.** Se establecen las siguientes modalidades de trabajo de grado para los estudiantes de Ingeniería de Sistemas:
1. **Pasantía**: Práctica en empresa u organización convenida.
2. **Monografía**: Proyecto de investigación formativa o disciplinar.
3. **Materias de Posgrado**: Aprobación de créditos en posgrados afines de la Universidad.

### CAPÍTULO II. DE LOS REQUISITOS Y PROCEDIMIENTOS

**Artículo 2. Requisitos de Inscripción.**
- Haber aprobado como mínimo el **80%** de los créditos académicos del pensum.
- Tener un promedio acumulado superior o igual a **3.2**.
- Contar con el aval del Consejo Curricular.

### CAPÍTULO III. VIGENCIA Y DEROGATORIAS

**Artículo 3. Vigencia.** El presente acuerdo rige a partir de la fecha de su expedición y deroga todas las disposiciones que le sean contrarias.`);
    if (!uploadTitle) setUploadTitle("Acuerdo N° 000 de 2026 - Modalidades de Grado");
    if (!uploadResolution) setUploadResolution("Acuerdo 000 de 2026");
  };

  const handleDeprecate = async (id: number, currentTitle: string) => {
    const reason = prompt(`¿Por qué motivo se deroga "${currentTitle}"? (Ej: Derogado por nuevo acuerdo):`);
    if (reason === null) return;

    try {
      await deprecateDocument(id, { reason });
      fetchDocs();
    } catch (err: any) {
      alert("Error al derogar documento: " + err.message);
    }
  };

  const handleDelete = async (id: number, title: string) => {
    if (!confirm(`¿Estás seguro de eliminar "${title}" y borrar todos sus fragmentos de ChromaDB?`)) return;
    try {
      await deleteDocument(id);
      fetchDocs();
    } catch (err: any) {
      alert("Error al eliminar: " + err.message);
    }
  };

  const handleSemanticTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testQuery.trim()) return;

    setIsSearching(true);
    try {
      const res = await testSemanticSearch(testQuery, 4);
      setSearchResults(res.results || []);
    } catch (err: any) {
      alert("Error en prueba semántica: " + err.message);
    } finally {
      setIsSearching(false);
    }
  };

  const filteredDocs = documents.filter((d) => {
    const matchesSearch =
      d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.resolution_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.filename.toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;
    if (validityFilter === "ALL") return true;
    return d.validity_status === validityFilter;
  });

  const getValidityBadge = (status: string) => {
    switch (status) {
      case "VIGENTE":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3" /> Vigente
          </span>
        );
      case "MODIFICADO":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            <GitBranch className="w-3 h-3" /> Modificado
          </span>
        );
      case "DEROGADO":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertOctagon className="w-3 h-3" /> Derogado / Inválido
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-stone-100 text-stone-600 border border-stone-200">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Module Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-stone-900 tracking-tight flex items-center gap-2">
            <Database className="w-5 h-5 text-[#C2410C]" />
            Base de Conocimiento & Linaje Normativo
          </h2>
          <p className="text-xs sm:text-sm text-stone-500 mt-0.5">
            Administra los acuerdos oficiales, convierte resoluciones PDF a Markdown y controla la vigencia en ChromaDB.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setUploadTab("markdown");
              setIsUploadOpen(true);
            }}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-stone-100 hover:bg-stone-200 text-stone-800 text-xs font-semibold rounded-xl transition border border-stone-200 shadow-xs"
          >
            <PenTool className="w-4 h-4 text-[#C2410C]" />
            <span>Redactar / Pegar Markdown</span>
          </button>
          <button
            onClick={() => {
              setUploadTab("file");
              setIsUploadOpen(true);
            }}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition shadow-xs"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Subir Archivo PDF / .md</span>
          </button>
        </div>
      </div>

      {/* Normative Lineage & Relationship Tree Card */}
      {(() => {
        const vigentesCount = documents.filter((d) => d.validity_status === "VIGENTE").length;
        const modificadosCount = documents.filter((d) => d.validity_status === "MODIFICADO").length;
        const derogadosCount = documents.filter((d) => d.validity_status === "DEROGADO").length;

        // Build normative relationship chains:
        // We want to map: [Active/Governing Document] -> [Superseded/Derogated Document]
        // 1. Group active documents by their supersedes_id target
        const relationsMap = new Map<number, {
          targetDoc: DocumentData | null;
          supersedingDocs: DocumentData[];
        }>();

        // Pass 1: find all docs with supersedes_id
        documents.forEach((d) => {
          if (d.supersedes_id) {
            if (!relationsMap.has(d.supersedes_id)) {
              const target = documents.find((item) => item.id === d.supersedes_id) || null;
              relationsMap.set(d.supersedes_id, { targetDoc: target, supersedingDocs: [] });
            }
            relationsMap.get(d.supersedes_id)!.supersedingDocs.push(d);
          }
        });

        // Pass 2: check derogated documents that have superseded_by_title or no supersedes_id link
        documents
          .filter((d) => d.validity_status === "DEROGADO" || d.superseded_by_title)
          .forEach((derogatedDoc) => {
            if (!relationsMap.has(derogatedDoc.id)) {
              // Try to find if any active document matches superseded_by_title
              const matchingActive = documents.filter((d) => {
                if (d.validity_status === "DEROGADO") return false;
                if (!derogatedDoc.superseded_by_title) return false;
                const needle = derogatedDoc.superseded_by_title.toLowerCase().trim();
                const hay = d.title.toLowerCase().trim();
                return hay.includes(needle) || needle.includes(hay);
              });
              relationsMap.set(derogatedDoc.id, {
                targetDoc: derogatedDoc,
                supersedingDocs: matchingActive,
              });
            }
          });

        const relationChains: Array<{
          id: string | number;
          primaryActiveDoc: DocumentData;
          companionDocs: DocumentData[];
          totalChunks: number;
          supersededDoc: DocumentData;
          relationshipType: "DEROGATORIA" | "MODIFICACION";
        }> = [];

        relationsMap.forEach(({ targetDoc, supersedingDocs }, targetId) => {
          if (!targetDoc) return;
          // Sort active docs by chunk_count descending so canonical document with most chunks is primary
          const sortedActive = [...supersedingDocs].sort((a, b) => (b.chunk_count || 0) - (a.chunk_count || 0));
          const primaryActive = sortedActive[0] || {
            id: -targetId,
            title: targetDoc.superseded_by_title || "Nueva Norma Oficial Vigente",
            filename: "oficial",
            file_type: "oficial",
            source_type: "OFICIAL",
            resolution_number: "Norma Vigente",
            effective_date: "",
            chunk_count: 0,
            status: "INDEXED",
            validity_status: "VIGENTE" as const,
          };

          const companionDocs = sortedActive.filter(
            (d) => d.id !== primaryActive.id && (d.chunk_count > 0 || d.source_type !== "EMAIL_BODY")
          );

          const totalChunks = sortedActive.reduce((acc, d) => acc + (d.chunk_count || 0), 0);
          const isMod = targetDoc.validity_status === "MODIFICADO";

          relationChains.push({
            id: `rel_${targetId}`,
            primaryActiveDoc: primaryActive,
            companionDocs,
            totalChunks: totalChunks || primaryActive.chunk_count || 0,
            supersededDoc: targetDoc,
            relationshipType: isMod ? "MODIFICACION" : "DEROGATORIA",
          });
        });

        // Set of document IDs involved in relations so they don't appear in standalone
        const involvedIds = new Set<number>();
        relationChains.forEach((r) => {
          if (r.supersededDoc?.id) involvedIds.add(r.supersededDoc.id);
          r.companionDocs.forEach((d) => involvedIds.add(d.id));
          if (r.primaryActiveDoc?.id && r.primaryActiveDoc.id > 0) involvedIds.add(r.primaryActiveDoc.id);
        });

        const standaloneDocs = documents.filter(
          (doc) => !involvedIds.has(doc.id) && doc.validity_status === "VIGENTE" && (doc.chunk_count > 0 || doc.source_type !== "EMAIL_BODY")
        );

        return (
          <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-amber-50 border border-amber-200/70 flex items-center justify-center">
                  <GitBranch className="w-4 h-4 text-[#C2410C]" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-stone-900">
                    Árbol de Relaciones y Linaje Normativo
                  </h3>
                  <p className="text-[11px] text-stone-400">
                    Mapeo dinámico de vigencias, modificaciones parciales y derogatorias activas en ChromaDB
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <span className="px-2.5 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200/80 rounded-lg">
                  {vigentesCount} Vigentes
                </span>
                {modificadosCount > 0 && (
                  <span className="px-2.5 py-1 bg-amber-50 text-amber-800 border border-amber-200/80 rounded-lg">
                    {modificadosCount} Modificadas
                  </span>
                )}
                {derogadosCount > 0 && (
                  <span className="px-2.5 py-1 bg-rose-50 text-rose-800 border border-rose-200/80 rounded-lg">
                    {derogadosCount} Derogadas
                  </span>
                )}
              </div>
            </div>

            {documents.length === 0 ? (
              <div className="py-8 px-4 text-center rounded-xl bg-stone-50 border border-dashed border-stone-200 space-y-1.5">
                <GitBranch className="w-7 h-7 text-stone-300 mx-auto" />
                <p className="text-xs font-semibold text-stone-600">
                  No hay acuerdos ni resoluciones registradas en la base de conocimiento
                </p>
                <p className="text-[11px] text-stone-400 max-w-md mx-auto">
                  Al cargar acuerdos o resoluciones oficiales en PDF, el sistema auditará las cláusulas de vigencia y derogatoria para conectar el árbol genealógico normativo en tiempo real.
                </p>
              </div>
            ) : relationChains.length === 0 && standaloneDocs.length > 0 ? (
              <div className="space-y-3 pt-1">
                <div className="flex items-center justify-between text-xs text-stone-500 bg-stone-50/70 p-2.5 rounded-xl border border-stone-100">
                  <span className="font-medium text-stone-600 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    Normas Pilares Activas (Sin conflictos ni derogaciones registradas)
                  </span>
                  <span className="text-[11px] text-stone-400">
                    {standaloneDocs.length} documento{standaloneDocs.length > 1 ? "s" : ""} indexado{standaloneDocs.length > 1 ? "s" : ""}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {standaloneDocs.map((doc) => (
                    <div
                      key={doc.id}
                      className="p-3.5 rounded-xl bg-white border border-stone-200 hover:border-amber-300 hover:shadow-xs transition space-y-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-bold text-stone-800 line-clamp-1">
                          {doc.title}
                        </span>
                        <span className="text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded font-semibold whitespace-nowrap">
                          Vigente
                        </span>
                      </div>
                      <p className="text-xs text-stone-600 font-medium">
                        {doc.resolution_number || "Documento Oficial"}
                      </p>
                      <div className="flex items-center justify-between text-[11px] text-stone-500 pt-1.5 border-t border-stone-100">
                        <span className="text-stone-400">
                          {doc.effective_date || "Fecha institucional"}
                        </span>
                        <span className="font-mono text-stone-600 bg-stone-100 px-1.5 py-0.2 rounded">
                          {doc.chunk_count} fragmentos
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-3 pt-1">
                <div className="grid grid-cols-1 gap-3">
                  {relationChains.map(({ id, primaryActiveDoc, companionDocs, totalChunks, supersededDoc, relationshipType }) => (
                    <div
                      key={id}
                      className="p-4 rounded-xl bg-stone-50/90 border border-stone-200 space-y-3 shadow-xs"
                    >
                      {/* Active Norm (Governing) */}
                      <div className="p-3 bg-white rounded-lg border border-emerald-200/80 shadow-xs space-y-1.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-stone-900">{primaryActiveDoc.title}</span>
                            <span className="text-[10px] text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded font-semibold border border-emerald-200">
                              {primaryActiveDoc.validity_status || "VIGENTE"}
                            </span>
                            {primaryActiveDoc.resolution_number && (
                              <span className="text-[11px] text-stone-500 font-mono">
                                ({primaryActiveDoc.resolution_number})
                              </span>
                            )}
                          </div>
                          <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-mono">
                            {totalChunks} fragmentos activos en ChromaDB
                          </span>
                        </div>

                        {companionDocs.length > 0 && (
                          <div className="text-[11px] text-stone-500 pt-1 border-t border-stone-100 flex flex-wrap gap-2">
                            <span className="font-medium text-stone-600">Archivos anexos vinculados:</span>
                            {companionDocs.map((comp) => (
                              <span key={comp.id} className="bg-stone-100 px-1.5 py-0.5 rounded text-stone-700 font-mono">
                                {comp.title} ({comp.chunk_count} chunks)
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Directional Connector Arrow */}
                      <div className="flex items-center gap-2 pl-3 text-xs font-semibold text-amber-800">
                        <CornerDownRight className="w-4 h-4 text-amber-600" />
                        <span>
                          {relationshipType === "MODIFICACION"
                            ? "Modifica formalmente a:"
                            : "Derogó normativamente a:"}
                        </span>
                      </div>

                      {/* Superseded / Derogated Norm */}
                      <div className="ml-4 p-3 rounded-lg bg-rose-50/50 border border-rose-200/90 flex flex-wrap items-center justify-between gap-2 text-xs">
                        <div className="flex items-center gap-2">
                          <AlertOctagon className="w-4 h-4 text-rose-600 shrink-0" />
                          <div>
                            <span className="font-semibold text-stone-900 line-clamp-1">
                              {supersededDoc.title}
                            </span>
                            {supersededDoc.resolution_number && (
                              <p className="text-[11px] text-stone-500 font-mono">
                                {supersededDoc.resolution_number}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-mono text-stone-500">
                            {supersededDoc.chunk_count === 0 ? "0 fragmentos" : `${supersededDoc.chunk_count} fragmentos`}
                          </span>
                          <span className="text-[10px] font-bold text-rose-700 bg-rose-100 px-2 py-0.5 rounded border border-rose-200">
                            {supersededDoc.validity_status || "DEROGADO"} (Excluido de RAG)
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}

                  {standaloneDocs.length > 0 && (
                    <div className="pt-2">
                      <span className="text-xs font-bold text-stone-700 block mb-2">
                        Otras Normas Base Vigentes:
                      </span>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
                        {standaloneDocs.map((doc) => (
                          <div
                            key={doc.id}
                            className="p-3 rounded-lg bg-white border border-stone-200 space-y-1"
                          >
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-semibold text-stone-900 line-clamp-1">
                                {doc.title}
                              </span>
                              <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded font-medium">
                                Vigente
                              </span>
                            </div>
                            <p className="text-[11px] text-stone-500">
                              {doc.resolution_number} • {doc.chunk_count} fragmentos
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* Documents Table */}
      <div className="bg-white rounded-2xl border border-stone-200 shadow-xs overflow-hidden">
        {/* Table Toolbar */}
        <div className="p-4 border-b border-stone-200 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {["ALL", "VIGENTE", "MODIFICADO", "DEROGADO"].map((st) => {
              const count = documents.filter((d) => (st === "ALL" ? true : d.validity_status === st)).length;
              const labels: Record<string, string> = {
                ALL: "Todos los Documentos",
                VIGENTE: "Vigentes",
                MODIFICADO: "Modificados",
                DEROGADO: "Derogados",
              };
              const active = validityFilter === st;

              return (
                <button
                  key={st}
                  onClick={() => setValidityFilter(st)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium transition flex items-center gap-1.5 ${
                    active ? "bg-[#C2410C] text-white" : "bg-stone-100/80 hover:bg-stone-200/60 text-stone-600"
                  }`}
                >
                  <span>{labels[st]}</span>
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${active ? "bg-white/20 text-white" : "bg-stone-200 text-stone-700"}`}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar documento o resolución..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-xl focus:ring-2 focus:ring-[#C2410C]/20 focus:border-[#C2410C]"
            />
          </div>
        </div>

        {/* Table Content */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-stone-600">
            <thead className="bg-stone-50/80 text-stone-500 font-semibold border-b border-stone-200">
              <tr>
                <th className="p-3.5 pl-5">Documento / Resolución</th>
                <th className="p-3.5">Número Oficial</th>
                <th className="p-3.5">Estado de Vigencia</th>
                <th className="p-3.5">Fragmentos Vectoriales</th>
                <th className="p-3.5">Fecha Efectiva</th>
                <th className="p-3.5 pr-5 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-stone-400">
                    No se encontraron documentos normativos con los filtros seleccionados.
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-stone-50/60 transition">
                    <td className="p-3.5 pl-5">
                      <div className="flex items-center gap-2.5">
                        <FileText className="w-4 h-4 text-[#C2410C] shrink-0" />
                        <div>
                          <p className="font-semibold text-stone-900 line-clamp-1">{doc.title}</p>
                          <p className="text-[11px] text-stone-400 font-mono">{doc.filename}</p>
                        </div>
                      </div>
                    </td>

                    <td className="p-3.5 font-medium text-stone-800">
                      {doc.resolution_number}
                    </td>

                    <td className="p-3.5">
                      {getValidityBadge(doc.validity_status)}
                    </td>

                    <td className="p-3.5 font-mono text-stone-700">
                      {doc.validity_status === "DEROGADO" ? (
                        <span className="text-[11px] text-rose-600 font-medium bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200">
                          0 chunks (purgado de RAG)
                        </span>
                      ) : doc.source_type === "EMAIL_BODY" && doc.chunk_count === 0 ? (
                        <span className="text-[11px] text-stone-400 italic bg-stone-100 px-1.5 py-0.5 rounded" title="El contenido se indexó en los documentos oficiales adjuntos">
                          0 chunks (en anexos)
                        </span>
                      ) : (
                        <span><span className="font-semibold">{doc.chunk_count}</span> chunks</span>
                      )}
                    </td>

                    <td className="p-3.5 text-stone-500">
                      {doc.effective_date || "N/A"}
                    </td>

                    <td className="p-3.5 pr-5 text-right space-x-2">
                      {doc.has_scan_image && (
                        <a
                          href={doc.scan_url || `/api/v1/documents/${doc.id}/scan`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-orange-800 hover:text-orange-950 bg-orange-100 hover:bg-orange-200 border border-orange-200 rounded-lg transition"
                          title="Ver imagen o escaneo original adjunto"
                        >
                          <Camera className="w-3 h-3 text-[#C2410C]" />
                          <span>Escaneo</span>
                        </a>
                      )}

                      <a
                        href={getDocumentPdfUrl(doc.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-stone-700 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 rounded-lg transition"
                        title="Ver documento original en nueva ventana"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>{doc.file_type === "pdf" ? "Ver PDF" : "Ver Documento"}</span>
                      </a>

                      {doc.validity_status !== "DEROGADO" && (
                        <button
                          onClick={() => handleDeprecate(doc.id, doc.title)}
                          className="px-2.5 py-1 text-xs font-medium text-amber-700 hover:text-amber-900 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg transition"
                          title="Marcar como derogado y desindexar de ChromaDB"
                        >
                          Derogar
                        </button>
                      )}

                      <button
                        onClick={() => handleDelete(doc.id, doc.title)}
                        className="p-1 text-stone-400 hover:text-rose-600 hover:bg-rose-50 rounded transition"
                        title="Eliminar permanentemente"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Live Semantic Search Test Card */}
      <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-xs space-y-4">
        <div className="flex items-center gap-2">
          <Search className="w-4 h-4 text-[#C2410C]" />
          <h3 className="text-sm font-bold text-stone-900">
            Prueba de Búsqueda Semántica en ChromaDB (Inspector RAG)
          </h3>
        </div>
        <p className="text-xs text-stone-500">
          Ejecuta una consulta de prueba directamente contra los embeddings de la base vectorial para verificar qué fragmentos y resoluciones recuperaría el asistente para un estudiante.
        </p>

        <form onSubmit={handleSemanticTest} className="flex gap-2">
          <input
            type="text"
            value={testQuery}
            onChange={(e) => setTestQuery(e.target.value)}
            placeholder="Ejemplo: ¿Qué promedio necesito para pasantía y cuántos créditos?"
            className="flex-1 p-2.5 text-xs bg-stone-50 border border-stone-200 rounded-xl focus:ring-2 focus:ring-[#C2410C]/20 focus:border-[#C2410C]"
          />
          <button
            type="submit"
            disabled={isSearching}
            className="px-4 py-2.5 bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold rounded-xl transition flex items-center gap-1.5 disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>{isSearching ? "Buscando..." : "Consultar ChromaDB"}</span>
          </button>
        </form>

        {searchResults.length > 0 && (
          <div className="mt-3 space-y-2.5 pt-2 border-t border-stone-100">
            <p className="text-xs font-semibold text-stone-700">
              Fragmentos recuperados más cercanos ({searchResults.length}):
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {searchResults.map((res, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-stone-50 border border-stone-200 text-xs space-y-1.5 font-sans"
                >
                  <div className="flex items-center justify-between text-stone-500 font-mono text-[11px]">
                    <span className="font-semibold text-[#C2410C]">
                      {res.metadata?.title || "Resolución Oficial"}
                    </span>
                    <span>Distancia: {typeof res.distance === "number" ? res.distance.toFixed(3) : "N/A"}</span>
                  </div>
                  <p className="text-stone-800 line-clamp-4 leading-relaxed whitespace-pre-wrap">
                    {res.content}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Upload Resolution & Direct Markdown Modal */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 overflow-y-auto">
          <div className="bg-white max-w-2xl w-full rounded-2xl border border-stone-200 shadow-2xl p-6 space-y-4 animate-in fade-in zoom-in-95 my-8">
            <div className="flex items-center justify-between pb-3 border-b border-stone-100">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center text-[#C2410C]">
                  {uploadTab === "file" ? <UploadCloud className="w-4 h-4" /> : <PenTool className="w-4 h-4" />}
                </div>
                <div>
                  <h3 className="text-base font-bold text-stone-900">
                    {uploadTab === "file" ? "Cargar Archivo de Resolución / Acuerdo" : "Redactar o Pegar Acuerdo en Markdown"}
                  </h3>
                  <p className="text-[11px] text-stone-400">
                    Indexación canónica con extracción semántica y auditoría de vigencia
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsUploadOpen(false)}
                className="text-stone-400 hover:text-stone-700 text-lg leading-none p-1 rounded-lg hover:bg-stone-100"
              >
                &times;
              </button>
            </div>

            {/* Mode Switcher Tabs */}
            <div className="flex items-center gap-2 p-1 bg-stone-100 rounded-xl">
              <button
                type="button"
                onClick={() => setUploadTab("file")}
                className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition ${
                  uploadTab === "file"
                    ? "bg-white text-stone-900 shadow-xs border border-stone-200"
                    : "text-stone-500 hover:text-stone-900"
                }`}
              >
                <UploadCloud className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Subir Archivo (PDF / .md / .txt)</span>
              </button>
              <button
                type="button"
                onClick={() => setUploadTab("markdown")}
                className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition ${
                  uploadTab === "markdown"
                    ? "bg-white text-stone-900 shadow-xs border border-stone-200"
                    : "text-stone-500 hover:text-stone-900"
                }`}
              >
                <PenTool className="w-3.5 h-3.5 text-[#C2410C]" />
                <span>Escribir / Pegar Markdown Directo</span>
              </button>
            </div>

            {uploadTab === "file" ? (
              <form onSubmit={handleUpload} className="space-y-4 text-xs">
                <div className="p-4 border-2 border-dashed border-stone-200 rounded-xl text-center bg-stone-50 hover:bg-stone-100/80 transition cursor-pointer">
                  <input
                    type="file"
                    accept=".pdf,.md,.markdown,.txt"
                    required
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="w-full text-xs text-stone-600 file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#C2410C] file:text-white hover:file:bg-[#9A3412]"
                  />
                  <p className="text-[11px] text-stone-400 mt-1">
                    Archivos soportados: PDF (con texto extraíble), Markdown (.md) y Texto (.txt).
                  </p>
                </div>

                <div>
                  <label className="font-semibold text-stone-700 block mb-1">
                    Título del Documento *
                  </label>
                  <input
                    type="text"
                    required
                    value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                    placeholder="Ej: Reglamento de Modalidades de Grado 2026"
                    className="w-full p-2.5 bg-stone-50 border border-stone-200 rounded-xl"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="font-semibold text-stone-700 block mb-1">
                      Número de Resolución / Acuerdo
                    </label>
                    <input
                      type="text"
                      value={uploadResolution}
                      onChange={(e) => setUploadResolution(e.target.value)}
                      placeholder="Ej: Acuerdo 012 de 2022"
                      className="w-full p-2.5 bg-stone-50 border border-stone-200 rounded-xl"
                    />
                  </div>
                  <div>
                    <label className="font-semibold text-stone-700 block mb-1">
                      Fecha de Entrada en Vigencia
                    </label>
                    <input
                      type="date"
                      value={uploadDate}
                      onChange={(e) => setUploadDate(e.target.value)}
                      className="w-full p-2.5 bg-stone-50 border border-stone-200 rounded-xl"
                    />
                  </div>
                </div>

                <div>
                  <label className="font-semibold text-stone-700 block mb-1">
                    ¿Deroga o reemplaza a un documento existente? (Opcional)
                  </label>
                  <select
                    value={supersedesDocId}
                    onChange={(e) => setSupersedesDocId(e.target.value)}
                    className="w-full p-2.5 bg-stone-50 border border-stone-200 rounded-xl text-stone-700"
                  >
                    <option value="">Ninguno (Es una norma nueva o complementaria)</option>
                    {documents.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.title} ({d.resolution_number})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-stone-100">
                  <button
                    type="button"
                    onClick={() => setIsUploadOpen(false)}
                    className="px-4 py-2 text-stone-600 hover:bg-stone-100 rounded-xl font-medium"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={isUploading}
                    className="px-4 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white font-semibold rounded-xl shadow-xs disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <UploadCloud className="w-4 h-4" />
                    <span>{isUploading ? "Indexando a ChromaDB..." : "Procesar e Indexar"}</span>
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleCreateMarkdown} className="space-y-4 text-xs">
                <div className="bg-amber-50/80 border border-amber-200/80 rounded-xl p-3 text-amber-900 flex items-start gap-2.5">
                  <Info className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                  <p className="text-[11.5px] leading-relaxed">
                    <strong>¿El acuerdo llegó escaneado como imagen?</strong> Pásalo por tu IA preferida (ChatGPT, Claude o Gemini) pidiéndole que transcriba fielmente los artículos en formato Markdown y pégalo a continuación. El sistema auditará artículos, derogatorias y lo indexará en la base vectorial oficial.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="font-semibold text-stone-700 block mb-1">
                      Título del Documento *
                    </label>
                    <input
                      type="text"
                      required
                      value={uploadTitle}
                      onChange={(e) => setUploadTitle(e.target.value)}
                      placeholder="Ej: Acuerdo 012 de 2022 - Reglamento de Grado"
                      className="w-full p-2.5 bg-stone-50 border border-stone-200 rounded-xl"
                    />
                  </div>
                  <div>
                    <label className="font-semibold text-stone-700 block mb-1">
                      Número de Resolución / Acuerdo
                    </label>
                    <input
                      type="text"
                      value={uploadResolution}
                      onChange={(e) => setUploadResolution(e.target.value)}
                      placeholder="Ej: Acuerdo 012 de 2022"
                      className="w-full p-2.5 bg-stone-50 border border-stone-200 rounded-xl"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="font-semibold text-stone-700 block mb-1">
                      Fecha de Entrada en Vigencia
                    </label>
                    <input
                      type="date"
                      value={uploadDate}
                      onChange={(e) => setUploadDate(e.target.value)}
                      className="w-full p-2.5 bg-stone-50 border border-stone-200 rounded-xl"
                    />
                  </div>
                  <div>
                    <label className="font-semibold text-stone-700 block mb-1">
                      ¿Deroga a otro documento? (Opcional)
                    </label>
                    <select
                      value={supersedesDocId}
                      onChange={(e) => setSupersedesDocId(e.target.value)}
                      className="w-full p-2.5 bg-stone-50 border border-stone-200 rounded-xl text-stone-700"
                    >
                      <option value="">Ninguno (Norma complementaria/nueva)</option>
                      {documents.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.title} ({d.resolution_number})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Optional Original Scan / Image Attachment */}
                <div className="space-y-1.5 p-3.5 bg-orange-50/40 border border-orange-200/60 rounded-xl">
                  <div className="flex items-center justify-between">
                    <label className="font-semibold text-stone-800 text-xs flex items-center gap-1.5">
                      <Camera className="w-3.5 h-3.5 text-[#C2410C]" />
                      <span>Adjuntar Imagen o Escaneo del Acuerdo (Opcional)</span>
                    </label>
                    {uploadScanFile && (
                      <button
                        type="button"
                        onClick={() => {
                          setUploadScanFile(null);
                          if (scanPreviewUrl) URL.revokeObjectURL(scanPreviewUrl);
                          setScanPreviewUrl(null);
                        }}
                        className="text-[11px] font-medium text-rose-600 hover:underline"
                      >
                        Quitar archivo
                      </button>
                    )}
                  </div>
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg,.webp,.pdf"
                    onChange={(e) => {
                      const f = e.target.files?.[0] || null;
                      setUploadScanFile(f);
                      if (f && (f.type.startsWith("image/") || f.name.match(/\.(png|jpe?g|webp)$/i))) {
                        setScanPreviewUrl(URL.createObjectURL(f));
                      } else {
                        if (scanPreviewUrl) URL.revokeObjectURL(scanPreviewUrl);
                        setScanPreviewUrl(null);
                      }
                    }}
                    className="w-full text-xs text-stone-600 file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#C2410C] file:text-white hover:file:bg-[#9A3412]"
                  />
                  <p className="text-[11px] text-stone-500">
                    Sube la foto, escaneo o PDF (.png, .jpg, .webp, .pdf) emitido por Rectoría para respaldar con sellos y firmas oficiales.
                  </p>
                  {scanPreviewUrl && (
                    <div className="mt-2 text-center p-2 bg-white rounded-lg border border-orange-200 shadow-xs">
                      <img
                        src={scanPreviewUrl}
                        alt="Vista previa del escaneo adjunto"
                        className="max-h-36 mx-auto rounded object-contain border border-stone-200"
                      />
                      <span className="text-[10px] text-stone-500 mt-1 block font-medium">
                        Vista previa de la imagen escaneada adjunta
                      </span>
                    </div>
                  )}
                </div>

                {/* Markdown Editor Toolbar */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="font-semibold text-stone-700 flex items-center gap-1.5">
                      <FileCode className="w-3.5 h-3.5 text-[#C2410C]" />
                      <span>Cuerpo del Acuerdo en Markdown *</span>
                    </label>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleLoadTemplate}
                        className="text-[11px] font-semibold text-stone-600 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 px-2 py-0.5 rounded-md transition"
                      >
                        Insertar Plantilla UD
                      </button>
                      <div className="flex items-center bg-stone-100 rounded-lg p-0.5 border border-stone-200">
                        <button
                          type="button"
                          onClick={() => setPreviewMarkdown(false)}
                          className={`px-2 py-0.5 text-[11px] font-semibold rounded-md transition ${
                            !previewMarkdown
                              ? "bg-white text-stone-900 shadow-xs"
                              : "text-stone-500 hover:text-stone-900"
                          }`}
                        >
                          Editor
                        </button>
                        <button
                          type="button"
                          onClick={() => setPreviewMarkdown(true)}
                          className={`px-2 py-0.5 text-[11px] font-semibold rounded-md transition flex items-center gap-1 ${
                            previewMarkdown
                              ? "bg-white text-stone-900 shadow-xs"
                              : "text-stone-500 hover:text-stone-900"
                          }`}
                        >
                          <Eye className="w-3 h-3" />
                          <span>Vista Previa</span>
                        </button>
                      </div>
                    </div>
                  </div>

                  {!previewMarkdown ? (
                    <textarea
                      required
                      rows={12}
                      value={markdownContent}
                      onChange={(e) => setMarkdownContent(e.target.value)}
                      placeholder="# UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS&#10;## ACUERDO N°...&#10;&#10;Pega aquí el contenido en Markdown generado por la otra IA..."
                      className="w-full p-3 bg-stone-50 font-mono text-xs border border-stone-200 rounded-xl leading-relaxed focus:ring-2 focus:ring-[#C2410C]/20 focus:border-[#C2410C]"
                    />
                  ) : (
                    <div className="w-full p-4 bg-white border border-stone-200 rounded-xl max-h-[280px] overflow-y-auto text-xs leading-relaxed text-stone-800 space-y-2 font-sans">
                      {markdownContent.trim() ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {markdownContent}
                        </ReactMarkdown>
                      ) : (
                        <p className="text-stone-400 italic">No hay contenido para previsualizar. Escribe o pega Markdown en la pestaña Editor.</p>
                      )}
                    </div>
                  )}

                  <div className="flex items-center justify-between text-[11px] text-stone-400 font-mono px-1">
                    <span>{markdownContent.length} caracteres • {markdownContent.trim() ? markdownContent.trim().split(/\s+/).length : 0} palabras</span>
                    <span>Soporta tablas, viñetas y encabezados Markdown estándar</span>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-stone-100">
                  <button
                    type="button"
                    onClick={() => setIsUploadOpen(false)}
                    className="px-4 py-2 text-stone-600 hover:bg-stone-100 rounded-xl font-medium"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={isUploading || !markdownContent.trim()}
                    className="px-4 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white font-semibold rounded-xl shadow-xs disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <FileCheck className="w-4 h-4" />
                    <span>{isUploading ? "Indexando a ChromaDB..." : "Guardar e Indexar Markdown"}</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default KnowledgeBaseModule;

