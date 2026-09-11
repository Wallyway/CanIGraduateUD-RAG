"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import Image from "next/image";
import { X, ExternalLink } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
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
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Prevent background body scroll when modal is open on mobile
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

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
          className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-amber-300/90 hover:text-amber-200 transition-colors cursor-pointer"
          title="Ver fragmento oficial y detalles"
        >
          <Image
            src="/images/logo-ud-citation.png"
            alt="Logo UD"
            width={14}
            height={14}
            className="w-3.5 h-3.5 object-contain shrink-0"
          />
          <span className="truncate max-w-[170px] sm:max-w-[220px]">
            {citation.resolution || citation.title} {citation.article ? `• ${citation.article}` : ""}
          </span>
        </button>

        {pdfUrl && (
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2.5 py-1 border-l border-amber-500/20 text-amber-400/80 hover:text-amber-300 hover:bg-amber-500/20 transition-colors inline-flex items-center cursor-pointer"
            title="Abrir documento o PDF oficial en nueva pestaña"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>

      {mounted && typeof document !== "undefined" && createPortal(
        <AnimatePresence>
          {isOpen && (
            <div
              className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md"
              onClick={() => setIsOpen(false)}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 15 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 15 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                className="relative w-full max-w-lg max-h-[88dvh] sm:max-h-[85vh] flex flex-col bg-neutral-900 border-t sm:border border-white/15 rounded-t-[28px] sm:rounded-3xl shadow-[0_24px_60px_rgba(0,0,0,0.85)] backdrop-blur-2xl overflow-hidden"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Mobile handle indicator */}
                <div className="w-12 h-1 bg-white/20 rounded-full mx-auto mt-2.5 mb-1 sm:hidden shrink-0" />

                {/* Modal Header - Pinned at top */}
                <div className="flex items-center justify-between gap-3 px-5 pt-2 pb-3.5 sm:px-6 sm:pt-5 sm:pb-4 border-b border-white/10 shrink-0">
                  <div className="flex items-center gap-2.5 text-amber-400 min-w-0">
                    <div className="w-7 h-7 rounded-lg bg-amber-400/10 border border-amber-400/20 flex items-center justify-center shrink-0 p-1">
                      <Image
                        src="/images/logo-ud-citation.png"
                        alt="Logo UD"
                        width={18}
                        height={18}
                        className="w-full h-full object-contain"
                      />
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-semibold text-white text-sm md:text-base tracking-tight truncate">
                        Fuente Oficial UD
                      </h3>
                      <span className="text-[11px] text-neutral-400 font-normal block truncate">
                        Normativa institucional verificada
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => setIsOpen(false)}
                    className="text-neutral-400 hover:text-white p-2 rounded-full hover:bg-white/10 active:scale-95 transition shrink-0 min-w-[40px] min-h-[40px] flex items-center justify-center cursor-pointer"
                    aria-label="Cerrar ventana"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Modal Body - Scrollable */}
                <div className="flex-1 overflow-y-auto px-5 py-4 sm:px-6 sm:py-5 space-y-4 text-sm overscroll-contain">
                  <div>
                    <span className="text-neutral-500 text-[11px] block uppercase font-medium tracking-wider">
                      Documento
                    </span>
                    <p className="font-medium text-white tracking-tight text-sm sm:text-base leading-snug">
                      {citation.title}
                    </p>
                  </div>

                  {citation.resolution && (
                    <div>
                      <span className="text-neutral-500 text-[11px] block uppercase font-medium tracking-wider">
                        Resolución / Acuerdo
                      </span>
                      <p className="text-amber-300 font-medium text-xs sm:text-sm">
                        {citation.resolution}
                      </p>
                    </div>
                  )}

                  {citation.article && (
                    <div>
                      <span className="text-neutral-500 text-[11px] block uppercase font-medium tracking-wider">
                        Artículo / Sección
                      </span>
                      <p className="text-neutral-200 text-xs sm:text-sm">
                        {citation.article}
                      </p>
                    </div>
                  )}

                  <div className="pt-1">
                    <span className="text-neutral-500 text-[11px] block uppercase font-medium tracking-wider mb-1.5">
                      Fragmento Oficial Verificado
                    </span>
                    <div className="bg-black/60 border border-white/10 rounded-2xl p-4 text-xs leading-relaxed text-neutral-300 max-h-48 sm:max-h-56 overflow-y-auto whitespace-pre-wrap font-mono selection:bg-amber-500/30">
                      {citation.excerpt}
                    </div>
                  </div>
                </div>

                {/* Modal Footer - Pinned at bottom */}
                <div className="flex items-center justify-between gap-3 px-5 py-3.5 sm:px-6 sm:py-4 border-t border-white/10 bg-neutral-950/80 backdrop-blur-md shrink-0">
                  {pdfUrl ? (
                    <a
                      href={pdfUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-stone-950 font-semibold text-xs rounded-xl transition shadow-sm active:scale-95 min-h-[42px] cursor-pointer"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>Ver Documento / PDF</span>
                    </a>
                  ) : (
                    <div />
                  )}
                  <button
                    onClick={() => setIsOpen(false)}
                    className="px-5 py-2.5 bg-white/10 hover:bg-white/15 text-white text-xs font-medium rounded-xl border border-white/15 transition active:scale-95 min-h-[42px] cursor-pointer"
                  >
                    Cerrar
                  </button>
                </div>
              </motion.div>
            </div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </>
  );
};

