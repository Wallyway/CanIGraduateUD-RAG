"use client";

import React, { useState } from "react";
import { Check, X, ChevronDown, ChevronUp, Mail, Paperclip, Link2, Sparkles, Loader2 } from "lucide-react";
import { approveEmail, rejectEmail } from "@/lib/api";

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
  triage_summary: string;
  triage_reasoning: string;
  target_program: string;
  status: "PENDING_REVIEW" | "APPROVED_INDEXED" | "AUTO_INDEXED" | "REJECTED";
  reviewed_at: string | null;
}

interface TriageCardProps {
  notice: EmailNoticeData;
  onStatusChange?: (id: number, newStatus: string) => void;
}

export const TriageCard: React.FC<TriageCardProps> = ({ notice, onStatusChange }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleApprove = async () => {
    setIsProcessing(true);
    try {
      await approveEmail(notice.id);
      onStatusChange?.(notice.id, "APPROVED_INDEXED");
    } catch (e) {
      console.error("Error approving email", e);
      alert("Error al aprobar e indexar el comunicado.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    setIsProcessing(true);
    try {
      await rejectEmail(notice.id);
      onStatusChange?.(notice.id, "REJECTED");
    } catch (e) {
      console.error("Error rejecting email", e);
      alert("Error al rechazar el comunicado.");
    } finally {
      setIsProcessing(false);
    }
  };

  const getStatusBadge = () => {
    switch (notice.status) {
      case "APPROVED_INDEXED":
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-700/60">
            Aprobado e Indexado
          </span>
        );
      case "AUTO_INDEXED":
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-950/80 text-cyan-300 border border-cyan-700/60">
            Auto-Indexado (Agéntico)
          </span>
        );
      case "REJECTED":
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-800 text-zinc-400 border border-zinc-700">
            Rechazado / Descartado
          </span>
        );
      case "PENDING_REVIEW":
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-700/60 animate-pulse">
            Pendiente de Revisión
          </span>
        );
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-sm space-y-4 transition hover:border-zinc-700">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 border-b border-zinc-800 pb-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            {getStatusBadge()}
            <span className="text-xs px-2 py-0.5 rounded-full bg-red-950/60 text-amber-300 border border-red-900/40 font-medium">
              {notice.target_program}
            </span>
            {notice.received_at && (
              <span className="text-xs text-zinc-500">
                {new Date(notice.received_at).toLocaleDateString("es-CO", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
          </div>
          <h3 className="font-semibold text-zinc-100 text-base leading-snug">
            {notice.subject}
          </h3>
          <div className="flex items-center gap-1.5 text-xs text-zinc-400">
            <Mail className="w-3.5 h-3.5 text-zinc-500" />
            <span className="font-mono">{notice.sender}</span>
          </div>
        </div>

        {/* Relevance Score Pill */}
        <div className="flex items-center gap-2 sm:self-start bg-zinc-950 border border-zinc-800 px-3 py-1.5 rounded-lg">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <div className="text-right">
            <span className="text-xs text-zinc-400 block font-medium">Relevancia LLM</span>
            <span
              className={`font-bold text-sm ${
                notice.relevance_score >= 70
                  ? "text-emerald-400"
                  : notice.relevance_score >= 40
                  ? "text-amber-400"
                  : "text-zinc-400"
              }`}
            >
              {notice.relevance_score.toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* LLM Triage Analysis */}
      <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-lg p-3.5 space-y-2 text-xs">
        <div>
          <span className="text-amber-400/90 font-semibold block uppercase tracking-wider text-[10px]">
            Dictamen del Agente Clasificador
          </span>
          <p className="text-zinc-200 mt-0.5 leading-relaxed">
            {notice.triage_summary || "Sin resumen disponible."}
          </p>
        </div>
        {notice.triage_reasoning && (
          <p className="text-zinc-400 text-[11px] italic border-t border-zinc-800/60 pt-1.5">
            <strong>Justificación:</strong> {notice.triage_reasoning}
          </p>
        )}
      </div>

      {/* Attachments / URLs */}
      {(notice.attachment_paths?.length > 0 || notice.extracted_urls?.length > 0) && (
        <div className="flex flex-wrap gap-2 text-xs">
          {notice.attachment_paths?.map((att, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1.5 bg-zinc-800 px-2.5 py-1 rounded-md text-zinc-300 font-mono text-[11px]"
            >
              <Paperclip className="w-3 h-3 text-amber-400" />
              <span>{att}</span>
            </span>
          ))}
          {notice.extracted_urls?.map((url, i) => (
            <a
              key={i}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 rounded-md text-amber-300 font-mono text-[11px] truncate max-w-xs transition"
            >
              <Link2 className="w-3 h-3 text-amber-400" />
              <span className="truncate">{url}</span>
            </a>
          ))}
        </div>
      )}

      {/* Raw Email Toggle */}
      <div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 transition"
        >
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          <span>{isExpanded ? "Ocultar cuerpo del correo original" : "Ver cuerpo del correo original"}</span>
        </button>
        {isExpanded && (
          <div className="mt-2 p-3 bg-zinc-950 border border-zinc-800 rounded-lg text-xs font-mono text-zinc-300 max-h-56 overflow-y-auto whitespace-pre-wrap leading-relaxed">
            {notice.body_text}
          </div>
        )}
      </div>

      {/* Action Buttons for Pending Notices */}
      {notice.status === "PENDING_REVIEW" && (
        <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-zinc-800">
          <button
            onClick={handleReject}
            disabled={isProcessing}
            className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-red-300 hover:bg-red-950/30 border border-zinc-700/60 transition flex items-center gap-1.5 disabled:opacity-50"
          >
            <X className="w-3.5 h-3.5" />
            <span>Descartar / Rechazar</span>
          </button>
          <button
            onClick={handleApprove}
            disabled={isProcessing}
            className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition flex items-center gap-1.5 shadow-sm disabled:opacity-50"
          >
            {isProcessing ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Check className="w-3.5 h-3.5" />
            )}
            <span>Aprobar e Indexar en RAG</span>
          </button>
        </div>
      )}
    </div>
  );
};

