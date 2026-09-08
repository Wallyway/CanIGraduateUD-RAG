"use client";

import React, { useState } from "react";
import { BookOpen, FileText, X, ExternalLink } from "lucide-react";
import { getDocumentPdfUrl } from "@/lib/api";

interface Citation {
  title: string;
  resolution?: string;
  article?: string;
  source_type?: string;
  excerpt: string;
  pdf_url?: string;
  document_id?: number;
}

interface CitationBadgeProps {
  citation: Citation;
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({ citation }) => {
  const [isOpen, setIsOpen] = useState(false);

  const pdfUrl = citation.pdf_url
    ? citation.pdf_url.startsWith("http")
      ? citation.pdf_url
      : `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${citation.pdf_url}`
    : citation.document_id
    ? getDocumentPdfUrl(citation.document_id)
    : null;

  return (
    <>
      <div className="inline-flex items-center rounded-full bg-amber-500/10 border border-amber-500/25 hover:border-amber-500/40 transition-all duration-200 shadow-sm overflow-hidden group">
        <button
          onClick={() => setIsOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-amber-300/90 hover:text-amber-200 transition-colors"
          title="Ver fragmento oficial y detalles"
        >
          <BookOpen className="w-3 h-3 text-amber-400 shrink-0" />
          <span className="truncate max-w-[200px]">
            {citation.resolution || citation.title} {citation.article ? `• ${citation.article}` : ""}
          </span>
        </button>

        {pdfUrl && (
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2 py-1 border-l border-amber-500/20 text-amber-400/80 hover:text-amber-300 hover:bg-amber-500/20 transition-colors inline-flex items-center"
            title="Abrir PDF oficial en nueva pestaña"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fadeIn">
          <div className="relative w-full max-w-lg bg-neutral-900/95 border border-white/15 rounded-3xl p-6 md:p-7 shadow-[0_24px_50px_rgba(0,0,0,0.8)] space-y-5 backdrop-blur-2xl">
            <div className="flex items-start justify-between gap-3 border-b border-white/10 pb-3.5">
              <div className="flex items-center gap-2.5 text-amber-400">
                <div className="p-1.5 rounded-lg bg-amber-400/10 border border-amber-400/20">
                  <FileText className="w-4 h-4 text-amber-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-white text-sm md:text-base tracking-tight">
                    Fuente Oficial UD
                  </h3>
                  <span className="text-[11px] text-neutral-400 font-normal">Normativa institucional verificada</span>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-neutral-400 hover:text-white p-1.5 rounded-full hover:bg-white/10 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3.5 text-sm">
              <div>
                <span className="text-neutral-500 text-[11px] block uppercase font-medium tracking-wider">Documento</span>
                <p className="font-medium text-white tracking-tight">{citation.title}</p>
              </div>

              {citation.resolution && (
                <div>
                  <span className="text-neutral-500 text-[11px] block uppercase font-medium tracking-wider">Resolución / Acuerdo</span>
                  <p className="text-amber-300 font-medium">{citation.resolution}</p>
                </div>
              )}

              {citation.article && (
                <div>
                  <span className="text-neutral-500 text-[11px] block uppercase font-medium tracking-wider">Artículo / Sección</span>
                  <p className="text-neutral-200">{citation.article}</p>
                </div>
              )}

              <div className="pt-1">
                <span className="text-neutral-500 text-[11px] block uppercase font-medium tracking-wider mb-1.5">
                  Fragmento Oficial Verificado
                </span>
                <div className="bg-black/60 border border-white/10 rounded-2xl p-4 text-xs leading-relaxed text-neutral-300 max-h-52 overflow-y-auto whitespace-pre-wrap font-mono selection:bg-amber-500/30">
                  {citation.excerpt}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-white/10">
              {pdfUrl ? (
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-stone-950 font-semibold text-xs rounded-xl transition shadow-sm"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Ver PDF Oficial en pestaña nueva</span>
                </a>
              ) : (
                <div />
              )}
              <button
                onClick={() => setIsOpen(false)}
                className="px-5 py-2 bg-white/10 hover:bg-white/15 text-white text-xs font-medium rounded-xl border border-white/15 transition active:scale-95"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

