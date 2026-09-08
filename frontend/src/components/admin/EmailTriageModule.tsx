"use client";

import React, { useState, useEffect } from "react";
import {
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  Mail,
  FileText,
  ExternalLink,
  ChevronRight,
  Filter,
  CheckSquare,
  Square,
  AlertTriangle,
  RefreshCw,
  Edit3,
  Save,
  Tag,
  GraduationCap
} from "lucide-react";
import {
  getAdminEmails,
  approveEmail,
  rejectEmail,
  updateEmailMetadata,
  batchActionEmails
} from "@/lib/api";

export interface EmailNoticeData {
  id: number;
  sender: string;
  subject: string;
  body_text: string;
  received_at: string | null;
  has_attachments: boolean;
  attachment_paths: string[];
  extracted_urls: string[];
  is_relevant: boolean;
  relevance_score: number;
  triage_summary?: string;
  triage_reasoning?: string;
  target_program: string;
  status: "PENDING_REVIEW" | "APPROVED_INDEXED" | "REJECTED" | "AUTO_INDEXED";
  reviewed_at?: string | null;
}

interface EmailTriageModuleProps {
  onDataChanged?: () => void;
}

export function EmailTriageModule({ onDataChanged }: EmailTriageModuleProps) {
  const [emails, setEmails] = useState<EmailNoticeData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [selectedEmail, setSelectedEmail] = useState<EmailNoticeData | null>(null);
  const [checkedIds, setCheckedIds] = useState<number[]>([]);

  // Editing state for drawer
  const [isEditing, setIsEditing] = useState(false);
  const [editSubject, setEditSubject] = useState("");
  const [editSummary, setEditSummary] = useState("");
  const [editProgram, setEditProgram] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const fetchEmails = async () => {
    setIsLoading(true);
    try {
      const data = await getAdminEmails();
      setEmails(data);
      if (data.length > 0 && !selectedEmail) {
        setSelectedEmail(data[0]);
      } else if (selectedEmail) {
        const refreshed = data.find((d: EmailNoticeData) => d.id === selectedEmail.id);
        if (refreshed) setSelectedEmail(refreshed);
      }
    } catch (err) {
      console.error("Error cargando comunicados", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEmails();
  }, []);

  const handleSelectEmail = (em: EmailNoticeData) => {
    setSelectedEmail(em);
    setIsEditing(false);
    setEditSubject(em.subject);
    setEditSummary(em.triage_summary || "");
    setEditProgram(em.target_program || "Ingeniería de Sistemas");
  };

  const handleApprove = async (id: number) => {
    setActionLoading(id);
    try {
      await approveEmail(id);
      await fetchEmails();
      onDataChanged?.();
    } catch (e: any) {
      alert("Error al aprobar: " + e.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (id: number) => {
    setActionLoading(id);
    try {
      await rejectEmail(id);
      await fetchEmails();
      onDataChanged?.();
    } catch (e: any) {
      alert("Error al rechazar: " + e.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSaveEdit = async () => {
    if (!selectedEmail) return;
    setIsSaving(true);
    try {
      await updateEmailMetadata(selectedEmail.id, {
        subject: editSubject,
        triage_summary: editSummary,
        target_program: editProgram,
      });
      setIsEditing(false);
      await fetchEmails();
    } catch (e: any) {
      alert("Error al guardar: " + e.message);
    } finally {
      setIsSaving(false);
    }
  };

  const toggleCheck = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setCheckedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleSelectAll = () => {
    if (checkedIds.length === filteredEmails.length) {
      setCheckedIds([]);
    } else {
      setCheckedIds(filteredEmails.map((e) => e.id));
    }
  };

  const handleBatchAction = async (action: "approve" | "reject") => {
    if (checkedIds.length === 0) return;
    const confirmText =
      action === "approve"
        ? `¿Aprobar e indexar ${checkedIds.length} comunicados seleccionados?`
        : `¿Rechazar ${checkedIds.length} comunicados seleccionados?`;

    if (!confirm(confirmText)) return;

    try {
      await batchActionEmails(checkedIds, action);
      setCheckedIds([]);
      await fetchEmails();
      onDataChanged?.();
    } catch (e: any) {
      alert("Error en acción en lote: " + e.message);
    }
  };

  const filteredEmails = emails.filter((em) => {
    const matchesSearch =
      em.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      em.sender.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (em.triage_summary && em.triage_summary.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    if (statusFilter === "ALL") return true;
    if (statusFilter === "PENDING") return em.status === "PENDING_REVIEW";
    if (statusFilter === "APPROVED")
      return em.status === "APPROVED_INDEXED" || em.status === "AUTO_INDEXED";
    if (statusFilter === "REJECTED") return em.status === "REJECTED";
    return true;
  });

  const getScoreBadge = (score: number) => {
    if (score >= 85) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-800 border border-emerald-200/80">
          <Sparkles className="w-3 h-3 text-emerald-600" />
          {score.toFixed(0)}% Relevante
        </span>
      );
    } else if (score >= 50) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200/80">
          <Clock className="w-3 h-3 text-amber-600" />
          {score.toFixed(0)}% Dudoso
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-stone-100 text-stone-600 border border-stone-200">
          {score.toFixed(0)}% Descartable
        </span>
      );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "APPROVED_INDEXED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3" /> Indexado
          </span>
        );
      case "AUTO_INDEXED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
            <Sparkles className="w-3 h-3" /> Auto-Indexado
          </span>
        );
      case "REJECTED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-stone-100 text-stone-500 border border-stone-200">
            <XCircle className="w-3 h-3" /> Desechado
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
            <Clock className="w-3 h-3" /> Pendiente
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-stone-200 shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-stone-900 tracking-tight flex items-center gap-2">
            <Mail className="w-5 h-5 text-[#C2410C]" />
            Bandeja & Triage de Comunicados
          </h2>
          <p className="text-xs sm:text-sm text-stone-500 mt-0.5">
            Evalúa la pertinencia académica calculada por IA y aprueba la indexación a ChromaDB.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchEmails}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-stone-700 bg-stone-50 hover:bg-stone-100 border border-stone-200 rounded-xl transition shadow-xs"
            title="Refrescar lista"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-stone-500 ${isLoading ? "animate-spin" : ""}`} />
            <span>Actualizar</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white px-4 py-3 rounded-2xl border border-stone-200 shadow-xs">
        <div className="flex items-center gap-2">
          {["ALL", "PENDING", "APPROVED", "REJECTED"].map((st) => {
            const count = emails.filter((e) => {
              if (st === "ALL") return true;
              if (st === "PENDING") return e.status === "PENDING_REVIEW";
              if (st === "APPROVED") return e.status === "APPROVED_INDEXED" || e.status === "AUTO_INDEXED";
              if (st === "REJECTED") return e.status === "REJECTED";
              return true;
            }).length;

            const labels: Record<string, string> = {
              ALL: "Todos",
              PENDING: "Pendientes",
              APPROVED: "Indexados",
              REJECTED: "Desechados",
            };

            const active = statusFilter === st;
            return (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition flex items-center gap-1.5 ${
                  active
                    ? "bg-[#C2410C] text-white shadow-xs"
                    : "bg-stone-100/70 hover:bg-stone-200/60 text-stone-600"
                }`}
              >
                <span>{labels[st]}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                    active ? "bg-white/20 text-white" : "bg-stone-200 text-stone-700"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-3">
          {/* Batch Actions when items are checked */}
          {checkedIds.length > 0 && (
            <div className="flex items-center gap-1.5 animate-in fade-in">
              <span className="text-xs font-medium text-stone-600 mr-1">
                {checkedIds.length} seleccionados:
              </span>
              <button
                onClick={() => handleBatchAction("approve")}
                className="px-2.5 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg transition"
              >
                Aprobar
              </button>
              <button
                onClick={() => handleBatchAction("reject")}
                className="px-2.5 py-1 text-xs font-semibold text-stone-600 bg-stone-100 hover:bg-stone-200 border border-stone-200 rounded-lg transition"
              >
                Desechar
              </button>
            </div>
          )}

          {/* Search Box */}
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar en comunicados..."
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#C2410C]/20 focus:border-[#C2410C] transition"
            />
          </div>
        </div>
      </div>

      {/* Main Split View: Table List on Left, Detail Reader on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Email List Column */}
        <div className="lg:col-span-6 bg-white rounded-2xl border border-stone-200 shadow-xs overflow-hidden flex flex-col">
          <div className="p-3.5 bg-stone-50/70 border-b border-stone-200 flex items-center justify-between text-xs font-medium text-stone-500">
            <div className="flex items-center gap-2">
              <button
                onClick={handleSelectAll}
                className="p-1 text-stone-400 hover:text-stone-700 rounded transition"
                title="Seleccionar todos"
              >
                {checkedIds.length === filteredEmails.length && filteredEmails.length > 0 ? (
                  <CheckSquare className="w-4 h-4 text-[#C2410C]" />
                ) : (
                  <Square className="w-4 h-4" />
                )}
              </button>
              <span>{filteredEmails.length} comunicados encontrados</span>
            </div>
            <span>Ordenados por fecha de recepción</span>
          </div>

          <div className="divide-y divide-stone-100 max-h-[640px] overflow-y-auto">
            {filteredEmails.length === 0 ? (
              <div className="p-12 text-center text-stone-400">
                <Mail className="w-8 h-8 mx-auto mb-2 text-stone-300" />
                <p className="text-sm font-medium">No se encontraron comunicados</p>
                <p className="text-xs text-stone-400 mt-1">
                  Intenta cambiar el filtro o usa el simulador para enviar un correo de prueba.
                </p>
              </div>
            ) : (
              filteredEmails.map((em) => {
                const isSelected = selectedEmail?.id === em.id;
                const isChecked = checkedIds.includes(em.id);

                return (
                  <div
                    key={em.id}
                    onClick={() => handleSelectEmail(em)}
                    className={`p-4 transition cursor-pointer flex items-start gap-3 hover:bg-stone-50/80 ${
                      isSelected ? "bg-amber-50/50 border-l-4 border-l-[#C2410C]" : ""
                    }`}
                  >
                    <button
                      onClick={(e) => toggleCheck(em.id, e)}
                      className="mt-0.5 text-stone-400 hover:text-stone-700"
                    >
                      {isChecked ? (
                        <CheckSquare className="w-4 h-4 text-[#C2410C]" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-xs font-semibold text-stone-800 truncate">
                          {em.sender}
                        </span>
                        <span className="text-[11px] text-stone-400 whitespace-nowrap">
                          {em.received_at
                            ? new Date(em.received_at).toLocaleDateString("es-CO", {
                                day: "2-digit",
                                month: "short",
                              })
                            : "Reciente"}
                        </span>
                      </div>

                      <h4 className="text-sm font-medium text-stone-900 line-clamp-1 mb-1.5">
                        {em.subject}
                      </h4>

                      <div className="flex flex-wrap items-center gap-2">
                        {getScoreBadge(em.relevance_score)}
                        {getStatusBadge(em.status)}
                        {em.has_attachments && (
                          <span className="text-[11px] font-mono text-stone-500 bg-stone-100 px-1.5 py-0.2 rounded">
                            PDF
                          </span>
                        )}
                      </div>
                    </div>

                    <ChevronRight className={`w-4 h-4 text-stone-400 self-center ${isSelected ? "text-[#C2410C]" : ""}`} />
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Detail & Curation Reader Pane on Right */}
        <div className="lg:col-span-6 bg-white rounded-2xl border border-stone-200 shadow-xs p-6 space-y-6">
          {selectedEmail ? (
            <>
              {/* Header & Quick Actions */}
              <div className="flex flex-col gap-3 pb-4 border-b border-stone-100">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    {getStatusBadge(selectedEmail.status)}
                    {getScoreBadge(selectedEmail.relevance_score)}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        setIsEditing(!isEditing);
                        setEditSubject(selectedEmail.subject);
                        setEditSummary(selectedEmail.triage_summary || "");
                        setEditProgram(selectedEmail.target_program || "Ingeniería de Sistemas");
                      }}
                      className="p-1.5 text-stone-500 hover:text-stone-800 hover:bg-stone-100 rounded-lg transition"
                      title="Editar metadatos antes de aprobar"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>
                    {selectedEmail.status !== "APPROVED_INDEXED" && selectedEmail.status !== "AUTO_INDEXED" && (
                      <button
                        onClick={() => handleApprove(selectedEmail.id)}
                        disabled={actionLoading === selectedEmail.id}
                        className="px-3.5 py-1.5 bg-[#C2410C] hover:bg-[#9A3412] text-white text-xs font-semibold rounded-xl transition shadow-xs disabled:opacity-50 flex items-center gap-1.5"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Aprobar e Indexar</span>
                      </button>
                    )}
                    {selectedEmail.status !== "REJECTED" && (
                      <button
                        onClick={() => handleReject(selectedEmail.id)}
                        disabled={actionLoading === selectedEmail.id}
                        className="px-3 py-1.5 bg-stone-100 hover:bg-stone-200 text-stone-700 text-xs font-medium rounded-xl transition"
                      >
                        Desechar
                      </button>
                    )}
                  </div>
                </div>

                {isEditing ? (
                  <div className="space-y-3 pt-2">
                    <div>
                      <label className="text-xs font-semibold text-stone-600 block mb-1">
                        Asunto / Título Normativo
                      </label>
                      <input
                        type="text"
                        value={editSubject}
                        onChange={(e) => setEditSubject(e.target.value)}
                        className="w-full text-sm font-semibold p-2.5 bg-stone-50 border border-stone-200 rounded-xl focus:ring-2 focus:ring-[#C2410C]/20 focus:border-[#C2410C]"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-stone-600 block mb-1">
                        Programa Aplicable
                      </label>
                      <input
                        type="text"
                        value={editProgram}
                        onChange={(e) => setEditProgram(e.target.value)}
                        className="w-full text-xs p-2 bg-stone-50 border border-stone-200 rounded-xl"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-stone-600 block mb-1">
                        Resumen de Triage
                      </label>
                      <textarea
                        rows={2}
                        value={editSummary}
                        onChange={(e) => setEditSummary(e.target.value)}
                        className="w-full text-xs p-2.5 bg-stone-50 border border-stone-200 rounded-xl"
                      />
                    </div>
                    <button
                      onClick={handleSaveEdit}
                      disabled={isSaving}
                      className="px-3 py-1.5 bg-stone-900 hover:bg-stone-800 text-white text-xs font-medium rounded-xl flex items-center gap-1.5"
                    >
                      <Save className="w-3.5 h-3.5" />
                      <span>{isSaving ? "Guardando..." : "Guardar Cambios"}</span>
                    </button>
                  </div>
                ) : (
                  <div>
                    <h3 className="text-lg font-bold text-stone-900 leading-snug">
                      {selectedEmail.subject}
                    </h3>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-stone-500 mt-1">
                      <span>De: <strong className="text-stone-700">{selectedEmail.sender}</strong></span>
                      <span>•</span>
                      <span>
                        {selectedEmail.received_at
                          ? new Date(selectedEmail.received_at).toLocaleString("es-CO")
                          : "Fecha desconocida"}
                      </span>
                      <span>•</span>
                      <span className="flex items-center gap-1 text-[#C2410C] font-medium">
                        <GraduationCap className="w-3.5 h-3.5" />
                        {selectedEmail.target_program}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* AI Triage Card */}
              <div className="p-4 rounded-2xl bg-amber-50/60 border border-amber-200/80 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-[#C2410C]">
                    <Sparkles className="w-4 h-4" />
                    <span>Evaluación del Agente de Triage UD</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-amber-900">
                    Confianza: {selectedEmail.relevance_score.toFixed(0)}%
                  </span>
                </div>

                <p className="text-xs text-stone-700 leading-relaxed">
                  {selectedEmail.triage_summary || "Sin resumen de IA."}
                </p>

                {selectedEmail.triage_reasoning && (
                  <div className="text-[11.5px] text-stone-600 bg-white/70 p-2.5 rounded-xl border border-amber-200/50 leading-relaxed">
                    <strong className="text-stone-800 font-semibold block mb-0.5">
                      Justificación de relevancia:
                    </strong>
                    {selectedEmail.triage_reasoning}
                  </div>
                )}
              </div>

              {/* Body Content */}
              <div>
                <h4 className="text-xs font-semibold text-stone-700 uppercase tracking-wider mb-2">
                  Cuerpo del Comunicado
                </h4>
                <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200 max-h-72 overflow-y-auto text-xs sm:text-[13px] text-stone-800 leading-relaxed font-sans whitespace-pre-wrap select-text">
                  {selectedEmail.body_text}
                </div>
              </div>

              {/* Attachments Section */}
              {selectedEmail.has_attachments && selectedEmail.attachment_paths.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-stone-700 uppercase tracking-wider mb-2">
                    Documentos Adjuntos
                  </h4>
                  <div className="space-y-1.5">
                    {selectedEmail.attachment_paths.map((p, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2.5 rounded-xl bg-stone-50 border border-stone-200 text-xs text-stone-700"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText className="w-4 h-4 text-[#C2410C] shrink-0" />
                          <span className="truncate">{p}</span>
                        </div>
                        <span className="text-[11px] text-stone-400 font-medium">Adjunto</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="p-12 text-center text-stone-400">
              <Mail className="w-10 h-10 mx-auto mb-2 text-stone-300" />
              <p className="text-sm font-medium">Selecciona un comunicado para ver los detalles</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default EmailTriageModule;

