"use client";

import React, { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  MessageSquareHeart,
  Star,
  RefreshCw,
  Search,
  Filter,
  CheckCircle2,
  AlertCircle,
  Eye,
  Trash2,
  Download,
  Mail,
  FileText,
  X,
  Sparkles,
  Calendar,
  User,
  ShieldCheck,
  Check,
  ChevronRight,
  Clock
} from "lucide-react";
import {
  getSessionFeedbacks,
  updateFeedbackStatus,
  deleteFeedback
} from "@/lib/api";

export interface FeedbackItem {
  id: number;
  session_id: string | null;
  user_email: string | null;
  feedback_type: string;
  rating: number | null;
  comments: string;
  has_transcript: boolean;
  transcript_json: string | null;
  target_email: string;
  status: string;
  created_at: string | null;
}

export function SessionFeedbackModule() {
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [selectedTranscript, setSelectedTranscript] = useState<{
    feedbackId: number;
    sessionId: string | null;
    messages: any[];
  } | null>(null);

  const fetchFeedbacks = async () => {
    setIsLoading(true);
    try {
      const data = await getSessionFeedbacks(100);
      setFeedbacks(data || []);
    } catch (err) {
      console.error("Error al obtener feedbacks", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFeedbacks();
  }, []);

  const handleToggleStatus = async (item: FeedbackItem) => {
    const nextStatus = item.status === "REVIEWED" ? "RECEIVED" : "REVIEWED";
    try {
      await updateFeedbackStatus(item.id, nextStatus);
      setFeedbacks((prev) =>
        prev.map((f) => (f.id === item.id ? { ...f, status: nextStatus } : f))
      );
    } catch (err) {
      alert("Error al actualizar estado del feedback");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("¿Seguro que deseas eliminar este registro de feedback?")) return;
    try {
      await deleteFeedback(id);
      setFeedbacks((prev) => prev.filter((f) => f.id !== id));
    } catch (err) {
      alert("Error al eliminar feedback");
    }
  };

  const handleOpenTranscript = (item: FeedbackItem) => {
    if (!item.transcript_json) return;
    try {
      const parsed = JSON.parse(item.transcript_json);
      setSelectedTranscript({
        feedbackId: item.id,
        sessionId: item.session_id,
        messages: Array.isArray(parsed) ? parsed : [],
      });
    } catch (e) {
      alert("No se pudo procesar la transcripción de esta sesión.");
    }
  };

  const handleExportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(feedbacks, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `feedbacks_canigraduate_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  // KPIs
  const totalCount = feedbacks.length;
  const ratedFeedbacks = feedbacks.filter((f) => f.rating && f.rating > 0);
  const avgRating = ratedFeedbacks.length > 0
    ? (ratedFeedbacks.reduce((acc, f) => acc + (f.rating || 0), 0) / ratedFeedbacks.length).toFixed(1)
    : "N/A";
  const withTranscriptCount = feedbacks.filter((f) => f.has_transcript).length;
  const pendingCount = feedbacks.filter((f) => f.status !== "REVIEWED").length;

  // Filters
  const filteredFeedbacks = feedbacks.filter((f) => {
    if (typeFilter !== "ALL" && f.feedback_type !== typeFilter) return false;
    if (statusFilter === "NEW" && f.status === "REVIEWED") return false;
    if (statusFilter === "REVIEWED" && f.status !== "REVIEWED") return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchComment = f.comments?.toLowerCase().includes(q);
      const matchEmail = f.user_email?.toLowerCase().includes(q);
      const matchSession = f.session_id?.toLowerCase().includes(q);
      return matchComment || matchEmail || matchSession;
    }
    return true;
  });

  const getTypeBadge = (type: string) => {
    switch (type) {
      case "sugerencia":
        return <span className="px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">💡 Sugerencia</span>;
      case "informacion_imprecisa":
        return <span className="px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-rose-50 text-rose-800 border border-rose-200">⚠️ Imprecisión</span>;
      case "error_tecnico":
        return <span className="px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-red-50 text-red-800 border border-red-200">🐞 Error Técnico</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-stone-100 text-stone-700 border border-stone-200">💬 General</span>;
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Top Header Card */}
      <div className="bg-white p-5 sm:p-6 rounded-2xl border border-stone-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
              <MessageSquareHeart className="w-4 h-4" />
            </div>
            <h2 className="text-base sm:text-lg font-bold text-stone-900">
              Auditoría y Retroalimentación de Sesiones
            </h2>
          </div>
          <p className="text-xs text-stone-500 max-w-2xl leading-relaxed">
            Reportes, valoraciones y transcripciones enviadas por estudiantes. Permite verificar la precisión de las respuestas del modelo, detectar vacíos normativos y mejorar la atención institucional.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchFeedbacks}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-stone-700 bg-stone-100 hover:bg-stone-200 rounded-xl transition active:scale-95 disabled:opacity-50"
            title="Recargar feedbacks"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Actualizar</span>
          </button>
          <button
            onClick={handleExportJSON}
            disabled={feedbacks.length === 0}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-[#C2410C] hover:bg-[#EA580C] rounded-xl shadow-xs transition active:scale-95 disabled:opacity-50"
            title="Exportar reportes a JSON"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Exportar</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <div className="bg-white p-4 rounded-2xl border border-stone-200 shadow-xs space-y-1">
          <span className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
            Total Reportes
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-stone-900">{totalCount}</span>
            <span className="text-xs text-stone-500">recibidos</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-stone-200 shadow-xs space-y-1">
          <span className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
            Calificación Promedio
          </span>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold text-amber-600">{avgRating}</span>
            <div className="flex items-center text-amber-400">
              <Star className="w-4 h-4 fill-amber-400" />
            </div>
            <span className="text-xs text-stone-400">/ 5.0</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-stone-200 shadow-xs space-y-1">
          <span className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
            Con Transcripción
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-700">{withTranscriptCount}</span>
            <span className="text-xs text-stone-500">
              ({totalCount > 0 ? Math.round((withTranscriptCount / totalCount) * 100) : 0}%)
            </span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-stone-200 shadow-xs space-y-1">
          <span className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
            Pendientes de Revisión
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[#C2410C]">{pendingCount}</span>
            <span className="text-xs text-stone-500">por auditar</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-2xl border border-stone-200 shadow-xs flex flex-wrap items-center justify-between gap-3">
        {/* Category Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          {[
            { id: "ALL", label: "Todos los Tipos" },
            { id: "sugerencia", label: "💡 Sugerencias" },
            { id: "informacion_imprecisa", label: "⚠️ Imprecisiones" },
            { id: "error_tecnico", label: "🐞 Errores" },
            { id: "general", label: "💬 Generales" },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setTypeFilter(item.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition ${
                typeFilter === item.id
                  ? "bg-[#C2410C] text-white"
                  : "bg-stone-100 hover:bg-stone-200/70 text-stone-700"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Search & Status Filter */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-xl focus:ring-2 focus:ring-orange-500/20 text-stone-700"
          >
            <option value="ALL">Todos los Estados</option>
            <option value="NEW">Nuevos</option>
            <option value="REVIEWED">Revisados</option>
          </select>

          <div className="relative flex-1 sm:w-60">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar en comentarios o correo..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-xl focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 text-stone-800 placeholder-stone-400"
            />
          </div>
        </div>
      </div>

      {/* Feedback Cards List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="py-20 text-center space-y-3 bg-white rounded-2xl border border-stone-200">
            <div className="w-5 h-5 rounded-full border-2 border-orange-600 border-t-transparent animate-spin mx-auto" />
            <p className="text-xs text-stone-500">Cargando retroalimentación de estudiantes...</p>
          </div>
        ) : filteredFeedbacks.length === 0 ? (
          <div className="py-16 text-center space-y-2 bg-white rounded-2xl border border-dashed border-stone-200">
            <MessageSquareHeart className="w-8 h-8 text-stone-300 mx-auto" />
            <p className="text-sm font-semibold text-stone-700">No se encontraron reportes</p>
            <p className="text-xs text-stone-400 max-w-sm mx-auto">
              No hay reportes de feedback que coincidan con los filtros aplicados actualmente.
            </p>
          </div>
        ) : (
          filteredFeedbacks.map((item) => {
            const isReviewed = item.status === "REVIEWED";
            return (
              <div
                key={item.id}
                className={`p-5 rounded-2xl bg-white border transition-all shadow-xs space-y-3 ${
                  isReviewed
                    ? "border-stone-200 opacity-80"
                    : "border-amber-300/80 bg-gradient-to-br from-white to-amber-50/20"
                }`}
              >
                {/* Card Header */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    {getTypeBadge(item.feedback_type)}

                    {item.rating && (
                      <div className="flex items-center gap-1 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200 text-xs font-semibold text-amber-800">
                        <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-500" />
                        <span>{item.rating} / 5</span>
                      </div>
                    )}

                    <span
                      className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                        isReviewed
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-blue-50 text-blue-700 border border-blue-200"
                      }`}
                    >
                      {isReviewed ? "Revisado" : "Nuevo"}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-xs text-stone-400">
                    <Clock className="w-3.5 h-3.5 text-stone-400" />
                    <span>
                      {item.created_at
                        ? new Date(item.created_at).toLocaleString("es-CO", {
                            dateStyle: "medium",
                            timeStyle: "short",
                          })
                        : "Fecha no disponible"}
                    </span>
                  </div>
                </div>

                {/* Card Content: Comments */}
                <div className="p-3.5 rounded-xl bg-stone-50 border border-stone-100 text-stone-800 text-xs sm:text-sm leading-relaxed font-normal">
                  <p className="font-semibold text-stone-900 text-xs mb-1 text-stone-500 uppercase tracking-wide">
                    Observación del Estudiante:
                  </p>
                  <p className="whitespace-pre-wrap">{item.comments}</p>
                </div>

                {/* Card Footer: Metadata & Actions */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-stone-100 text-xs">
                  <div className="flex flex-wrap items-center gap-3 text-stone-500">
                    {item.user_email ? (
                      <span className="flex items-center gap-1 text-stone-700 font-medium">
                        <Mail className="w-3.5 h-3.5 text-stone-400" />
                        <span>{item.user_email}</span>
                      </span>
                    ) : (
                      <span className="text-stone-400 italic">Estudiante Anónimo</span>
                    )}

                    {item.session_id && (
                      <span className="text-[11px] font-mono text-stone-400 bg-stone-100 px-2 py-0.5 rounded">
                        Sesión: {item.session_id}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {item.has_transcript && (
                      <button
                        onClick={() => handleOpenTranscript(item)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-[#C2410C] bg-orange-50 hover:bg-orange-100 border border-orange-200 transition active:scale-95"
                        title="Ver conversación completa de la sesión"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Ver Conversación</span>
                      </button>
                    )}

                    <button
                      onClick={() => handleToggleStatus(item)}
                      className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-medium border transition active:scale-95 ${
                        isReviewed
                          ? "bg-stone-100 hover:bg-stone-200 text-stone-700 border-stone-200"
                          : "bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border-emerald-200 font-semibold"
                      }`}
                      title={isReviewed ? "Marcar como pendiente" : "Marcar como revisado"}
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>{isReviewed ? "Desmarcar" : "Revisado"}</span>
                    </button>

                    <button
                      onClick={() => handleDelete(item.id)}
                      className="p-1.5 text-stone-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                      title="Eliminar reporte"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Transcript Modal Dialog */}
      {selectedTranscript && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="w-full max-w-2xl max-h-[85vh] bg-white rounded-3xl border border-stone-200 shadow-2xl flex flex-col overflow-hidden animate-scaleIn">
            {/* Modal Header */}
            <div className="p-5 border-b border-stone-200 flex items-center justify-between bg-stone-50/80">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[#C2410C]" />
                  <h3 className="text-sm font-bold text-stone-900">
                    Transcripción de la Sesión de Chat
                  </h3>
                </div>
                <p className="text-[11px] text-stone-400 font-mono">
                  ID: {selectedTranscript.sessionId || `Feedback #${selectedTranscript.feedbackId}`} • {selectedTranscript.messages.length} turnos registrados
                </p>
              </div>

              <button
                onClick={() => setSelectedTranscript(null)}
                className="p-1.5 rounded-full text-stone-400 hover:text-stone-700 hover:bg-stone-200/70 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Conversation Thread */}
            <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-4 bg-stone-50/40">
              {selectedTranscript.messages.length === 0 ? (
                <p className="text-xs text-stone-400 text-center py-8">
                  No hay mensajes registrados en esta sesión.
                </p>
              ) : (
                selectedTranscript.messages.map((m: any, idx: number) => {
                  const isUser = m.role === "user";
                  return (
                    <div
                      key={idx}
                      className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                    >
                      <span className="text-[10px] font-semibold text-stone-400 mb-1 px-1">
                        {isUser ? "Estudiante" : "Can I Graduate AI"}
                      </span>
                      <div
                        className={`max-w-[88%] rounded-2xl p-4 text-xs sm:text-sm leading-relaxed ${
                          isUser
                            ? "bg-[#C2410C] text-white rounded-tr-xs shadow-xs"
                            : "bg-white text-stone-800 border border-stone-200 rounded-tl-xs shadow-xs"
                        }`}
                      >
                        {isUser ? (
                          <p className="whitespace-pre-wrap">{m.content}</p>
                        ) : (
                          <div className="prose prose-sm max-w-none text-stone-800">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {m.content}
                            </ReactMarkdown>

                            {m.citations && m.citations.length > 0 && (
                              <div className="mt-3 pt-2 border-t border-stone-100 flex flex-wrap gap-1.5">
                                <span className="text-[10px] font-semibold text-stone-500 block w-full">
                                  Citas invocadas:
                                </span>
                                {m.citations.map((c: any, cIdx: number) => (
                                  <span
                                    key={cIdx}
                                    className="bg-amber-50 text-amber-900 border border-amber-200 px-2 py-0.5 rounded text-[10px] font-mono"
                                  >
                                    {c.resolution || c.title}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-stone-200 bg-white flex items-center justify-end">
              <button
                onClick={() => setSelectedTranscript(null)}
                className="px-4 py-2 text-xs font-semibold rounded-xl bg-stone-100 hover:bg-stone-200 text-stone-700 transition"
              >
                Cerrar Transcripción
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

