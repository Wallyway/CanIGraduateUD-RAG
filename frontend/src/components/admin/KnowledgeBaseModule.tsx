"use client";

import React, { useState, useEffect } from "react";
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
  ShieldAlert,
  Info
} from "lucide-react";
import {
  getDocuments,
  uploadDocument,
  deleteDocument,
  deprecateDocument,
  testSemanticSearch,
  getDocumentPdfUrl
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
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadResolution, setUploadResolution] = useState("");
  const [uploadDate, setUploadDate] = useState("");
  const [supersedesDocId, setSupersedesDocId] = useState<string>("");
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
            onClick={() => setIsUploadOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition shadow-xs"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Subir Resolución PDF</span>
          </button>
        </div>
      </div>

      {/* Normative Lineage Tree Card */}
      <div className="bg-white p-5 rounded-2xl border border-stone-200 shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-[#C2410C]" />
            <h3 className="text-sm font-bold text-stone-900">
              Árbol de Relaciones y Derogaciones Normativas
            </h3>
          </div>
          <span className="text-xs text-stone-400">
            Previene respuestas contradictorias o normativas obsoletas en el RAG
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
          <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-200 space-y-1.5">
            <div className="flex items-center justify-between text-xs font-bold text-stone-800">
              <span>Modalidades de Grado</span>
              <span className="text-[10px] text-emerald-700 bg-emerald-100/70 px-1.5 py-0.2 rounded font-semibold">
                Activa
              </span>
            </div>
            <p className="text-xs text-stone-600 font-medium">Acuerdo 038 de 2015</p>
            <div className="flex items-center gap-1.5 text-[11px] text-stone-500 pt-1 border-t border-stone-200/60">
              <ArrowRight className="w-3 h-3 text-stone-400" />
              <span>Reglamenta pasantías, monografías y posgrados</span>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-200 space-y-1.5">
            <div className="flex items-center justify-between text-xs font-bold text-stone-800">
              <span>Requisito Inglés B2</span>
              <span className="text-[10px] text-emerald-700 bg-emerald-100/70 px-1.5 py-0.2 rounded font-semibold">
                Activa
              </span>
            </div>
            <p className="text-xs text-stone-600 font-medium">Acuerdo 004 de 2021 CSU</p>
            <div className="flex items-center gap-1.5 text-[11px] text-stone-500 pt-1 border-t border-stone-200/60">
              <ArrowRight className="w-3 h-3 text-stone-400" />
              <span>Acreditación ILUD y exámenes internacionales</span>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-200 space-y-1.5">
            <div className="flex items-center justify-between text-xs font-bold text-stone-800">
              <span>Estatuto Estudiantil</span>
              <span className="text-[10px] text-emerald-700 bg-emerald-100/70 px-1.5 py-0.2 rounded font-semibold">
                Activa
              </span>
            </div>
            <p className="text-xs text-stone-600 font-medium">Acuerdo 027 de 1993</p>
            <div className="flex items-center gap-1.5 text-[11px] text-stone-500 pt-1 border-t border-stone-200/60">
              <ArrowRight className="w-3 h-3 text-stone-400" />
              <span>Paz y salvos, reservas y deberes estudiantiles</span>
            </div>
          </div>
        </div>
      </div>

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
                      <span className="font-semibold">{doc.chunk_count}</span> chunks
                    </td>

                    <td className="p-3.5 text-stone-500">
                      {doc.effective_date || "N/A"}
                    </td>

                    <td className="p-3.5 pr-5 text-right space-x-2">
                      <a
                        href={getDocumentPdfUrl(doc.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-stone-700 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 rounded-lg transition"
                        title="Ver documento original en nueva ventana"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>Ver PDF</span>
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

      {/* Upload Resolution Modal */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white max-w-lg w-full rounded-2xl border border-stone-200 shadow-xl p-6 space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-stone-100">
              <h3 className="text-base font-bold text-stone-900 flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-[#C2410C]" />
                Subir Resolución o Acuerdo Oficial
              </h3>
              <button
                onClick={() => setIsUploadOpen(false)}
                className="text-stone-400 hover:text-stone-700 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleUpload} className="space-y-4 text-xs">
              <div className="p-4 border-2 border-dashed border-stone-200 rounded-xl text-center bg-stone-50 hover:bg-stone-100/80 transition cursor-pointer">
                <input
                  type="file"
                  accept=".pdf,.md,.txt"
                  required
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-stone-600 file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#C2410C] file:text-white hover:file:bg-[#9A3412]"
                />
                <p className="text-[11px] text-stone-400 mt-1">
                  Los PDFs se transformarán automáticamente a Markdown limpio para su indexación en ChromaDB.
                </p>
              </div>

              <div>
                <label className="font-semibold text-stone-700 block mb-1">
                  Título del Documento
                </label>
                <input
                  type="text"
                  required
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="Ej: Reglamento de Pasantías de Grado 2026"
                  className="w-full p-2.5 bg-stone-50 border border-stone-200 rounded-xl"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-stone-700 block mb-1">
                    Número de Resolución / Acuerdo
                  </label>
                  <input
                    type="text"
                    value={uploadResolution}
                    onChange={(e) => setUploadResolution(e.target.value)}
                    placeholder="Ej: Resolución 014 de 2026"
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
                <p className="text-[11px] text-amber-700 mt-1">
                  Si seleccionas un documento, quedará marcado como DEROGADO y sus fragmentos antiguos serán retirados de ChromaDB automáticamente.
                </p>
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
          </div>
        </div>
      )}
    </div>
  );
}

export default KnowledgeBaseModule;

