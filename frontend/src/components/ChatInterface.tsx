"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Sparkles,
  HelpCircle,
  MessageSquareHeart,
  Send,
  CheckCircle2,
  X,
  Star,
  Mail,
  Plus,
  Github,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { streamChat, getDocumentPdfUrl, sendSessionFeedback, checkBanStatus } from "@/lib/api";
import {
  ChatMessage,
  getStoredChatHistory,
  saveStoredChatHistory,
  clearStoredChatHistory,
} from "@/lib/storage";

function formatCountdown(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const seconds = safeSeconds % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}
import { CitationBadge } from "./CitationBadge";
import { MoltenMetal } from "./MoltenMetal";
import PromptInputBox from "./ui/ai-prompt-box";
import { ThinkingState, PixelDotsLoader, TraceNode } from "./ui/agent-trace";

const SUGGESTIONS = [
  {
    label: "Modalidades de grado",
    full: "¿Cuáles son todas las modalidades de grado disponibles?",
  },
  {
    label: "Requisitos de pasantía",
    full: "¿Qué requisitos y cuántos créditos necesito para hacer una pasantía?",
  },
  {
    label: "Acreditación de inglés B2",
    full: "¿Cómo acredito el requisito de inglés B2 en el ILUD?",
  },
  {
    label: "Paz y salvos para grado",
    full: "¿Qué paz y salvos debo solicitar para radicar mi carpeta de grado?",
  },
];

const buildDefaultTrace = (query: string): TraceNode[] => [
  {
    type: "search",
    primary: "Búsqueda de acuerdos y normatividad",
    secondary: "ChromaDB - Base Vectorial UD",
    sources: [
      { name: "Acuerdo 038 de 2015 (Modalidades de Grado)", url: "#" },
      { name: "Acuerdo 027 de 1993 (Estatuto Estudiantil)", url: "#" },
      { name: "Resolución 004 de 2021 (Acreditación B2)", url: "#" },
    ],
  },
  {
    type: "reasoning",
    sentences: [
      `Analizando la consulta: "${query.slice(0, 45)}${query.length > 45 ? "..." : ""}"`,
      "Identificando requisitos de créditos, paz y salvos y modalidades aplicables...",
      "Verificando vigencia de acuerdos del Consejo Superior y Académico...",
      "Formulando respuesta oficial sustentada con citas de artículos...",
    ],
    durationSeconds: 3.2,
  },
];

const STATIC_MARKDOWN_COMPONENTS = {
  p: ({ children }: any) => (
    <p className="text-[14.5px] sm:text-[15px] leading-[1.8] text-neutral-200/95 mb-4 font-normal tracking-[0.01em] text-pretty">
      {children}
    </p>
  ),
  h1: ({ children }: any) => (
    <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight mt-6 mb-3 flex items-center gap-2">
      {children}
    </h1>
  ),
  h2: ({ children }: any) => (
    <h2 className="text-base sm:text-lg font-semibold text-amber-300 tracking-tight mt-6 mb-3 flex items-center gap-2 pb-1.5 border-b border-white/[0.08]">
      {children}
    </h2>
  ),
  h3: ({ children }: any) => (
    <h3 className="text-[15px] sm:text-base font-semibold text-amber-200/90 tracking-tight mt-5 mb-2.5">
      {children}
    </h3>
  ),
  ul: ({ children }: any) => (
    <ul className="my-3.5 space-y-2.5 pl-1">
      {children}
    </ul>
  ),
  ol: ({ children }: any) => (
    <ol className="my-3.5 space-y-2.5 pl-1 list-decimal list-inside text-neutral-300">
      {children}
    </ol>
  ),
  li: ({ children, ordered }: any) => {
    if (ordered) {
      return (
        <li className="text-[14px] sm:text-[14.5px] leading-relaxed text-neutral-200/90 pl-1">
          {children}
        </li>
      );
    }
    return (
      <li className="flex items-start gap-2.5 text-[14px] sm:text-[14.5px] leading-relaxed text-neutral-200/90">
        <span className="size-1.5 rounded-full bg-amber-400 mt-2 shrink-0 shadow-[0_0_8px_rgba(251,191,36,0.6)]" />
        <span className="flex-1">{children}</span>
      </li>
    );
  },
  strong: ({ children }: any) => (
    <strong className="font-semibold text-white tracking-tight">
      {children}
    </strong>
  ),
  blockquote: ({ children }: any) => (
    <blockquote className="my-4 rounded-2xl border border-amber-500/20 bg-amber-500/[0.05] p-4 text-sm text-neutral-200/90 backdrop-blur-md relative overflow-hidden">
      <div className="absolute left-0 top-0 bottom-0 w-1 bg-amber-500/70" />
      <div className="pl-1.5">{children}</div>
    </blockquote>
  ),
  code: ({ inline, className, children, ...props }: any) => {
    if (inline) {
      return (
        <code className="px-1.5 py-0.5 rounded-md bg-white/[0.08] text-amber-300 font-mono text-[13px] border border-white/10">
          {children}
        </code>
      );
    }
    return (
      <div className="rounded-xl border border-white/10 bg-neutral-950/80 p-3.5 font-mono text-[12.5px] leading-relaxed text-neutral-200 overflow-x-auto my-3.5">
        <pre className="whitespace-pre">{children}</pre>
      </div>
    );
  },
  hr: () => (
    <hr className="my-5 border-white/[0.08]" />
  ),
};

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeAssistantId, setActiveAssistantId] = useState<string | null>(null);
  const [queueInfo, setQueueInfo] = useState<{ position: number; estimated_seconds: number } | null>(null);
  const [banState, setBanState] = useState<{
    isBanned: boolean;
    remainingSeconds: number;
    reason?: string;
  } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isHeroState = messages.length === 0;

  // Session & Feedback states
  const [sessionId, setSessionId] = useState<string>(() => {
    if (typeof window !== "undefined") {
      const storedId = sessionStorage.getItem("can_i_graduate_session_id");
      if (storedId) return storedId;
      const newId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
      sessionStorage.setItem("can_i_graduate_session_id", newId);
      return newId;
    }
    return `session_${Date.now()}`;
  });
  const [isFeedbackModalOpen, setIsFeedbackModalOpen] = useState(false);
  const [feedbackType, setFeedbackType] = useState<"sugerencia" | "informacion_imprecisa" | "error_tecnico" | "general">("general");
  const [feedbackRating, setFeedbackRating] = useState<number>(0);
  const [feedbackComments, setFeedbackComments] = useState("");
  const [feedbackUserEmail, setFeedbackUserEmail] = useState("");
  const [feedbackIncludeTranscript, setFeedbackIncludeTranscript] = useState(true);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);
  const [feedbackEmailSent, setFeedbackEmailSent] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [feedbackMailtoUrl, setFeedbackMailtoUrl] = useState<string | null>(null);
  const [feedbackGmailUrl, setFeedbackGmailUrl] = useState<string | null>(null);

  // Strictly prevent body & document scrolling in Hero State (landing screen)
  useEffect(() => {
    if (typeof window === "undefined") return;

    if (isHeroState) {
      document.documentElement.style.overflow = "hidden";
      document.body.style.overflow = "hidden";
      document.documentElement.style.overscrollBehavior = "none";
      document.body.style.overscrollBehavior = "none";
      document.documentElement.style.height = "100%";
      document.body.style.height = "100%";
    } else {
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
      document.documentElement.style.overscrollBehavior = "";
      document.body.style.overscrollBehavior = "";
      document.documentElement.style.height = "";
      document.body.style.height = "";
    }

    return () => {
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
      document.documentElement.style.overscrollBehavior = "";
      document.body.style.overscrollBehavior = "";
      document.documentElement.style.height = "";
      document.body.style.height = "";
    };
  }, [isHeroState]);

  // Check ban status on mount from localStorage and backend
  useEffect(() => {
    if (typeof window === "undefined") return;

    // 1. Immediate fast check from localStorage
    const storedBannedUntil = localStorage.getItem("ud_banned_until");
    const storedReason = localStorage.getItem("ud_banned_reason") || undefined;
    if (storedBannedUntil) {
      const banUntilMs = parseInt(storedBannedUntil, 10);
      const nowMs = Date.now();
      const remainingSec = Math.max(0, Math.ceil((banUntilMs - nowMs) / 1000));
      if (remainingSec > 0) {
        setBanState({
          isBanned: true,
          remainingSeconds: remainingSec,
          reason: storedReason,
        });
      } else {
        localStorage.removeItem("ud_banned_until");
        localStorage.removeItem("ud_banned_reason");
      }
    }

    // 2. Authoritative check with backend /ban-status
    checkBanStatus()
      .then((status) => {
        // If the request failed due to network or server error, preserve existing ban from localStorage
        if (status.error) {
          return;
        }
        if (status.is_banned && status.remaining_seconds > 0) {
          const banUntilMs = Date.now() + status.remaining_seconds * 1000;
          localStorage.setItem("ud_banned_until", banUntilMs.toString());
          if (status.reason) {
            localStorage.setItem("ud_banned_reason", status.reason);
          }
          setBanState({
            isBanned: true,
            remainingSeconds: status.remaining_seconds,
            reason: status.reason,
          });
        } else if (!status.is_banned) {
          // Explicit authoritative unban from backend
          localStorage.removeItem("ud_banned_until");
          localStorage.removeItem("ud_banned_reason");
          setBanState(null);
        }
      })
      .catch(() => {
        // Fallback to localStorage on network disconnect
      });
  }, []);

  // Active ban countdown timer (1-second tick)
  useEffect(() => {
    if (!banState?.isBanned || banState.remainingSeconds <= 0) return;

    const intervalId = setInterval(() => {
      setBanState((prev) => {
        if (!prev || !prev.isBanned) return null;
        const nextRemaining = prev.remainingSeconds - 1;
        if (nextRemaining <= 0) {
          localStorage.removeItem("ud_banned_until");
          localStorage.removeItem("ud_banned_reason");
          return null;
        }
        return {
          ...prev,
          remainingSeconds: nextRemaining,
        };
      });
    }, 1000);

    return () => clearInterval(intervalId);
  }, [banState?.isBanned]);

  useEffect(() => {
    const stored = getStoredChatHistory();
    if (stored.length > 0) {
      setMessages(stored);
    }
  }, []);

  // Synchronize browser history with chat state so mobile back gesture/button returns to hero state instead of exiting
  useEffect(() => {
    if (typeof window === "undefined") return;

    if (messages.length > 0) {
      if (window.location.hash !== "#chat") {
        window.history.pushState({ view: "chat" }, "", "#chat");
      }
    } else {
      if (window.location.hash === "#chat") {
        window.history.replaceState(null, "", window.location.pathname);
      }
    }
  }, [messages.length]);

  // Intercept mobile back gesture / popstate event
  useEffect(() => {
    if (typeof window === "undefined") return;

    const handlePopState = () => {
      // If feedback modal is open, back button closes the modal
      if (isFeedbackModalOpen) {
        setIsFeedbackModalOpen(false);
        return;
      }
      // If user was in chat session and hit back, return smoothly to hero state
      if (messages.length > 0 && window.location.hash !== "#chat") {
        clearStoredChatHistory();
        setMessages([]);
        const newId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
        sessionStorage.setItem("can_i_graduate_session_id", newId);
        setSessionId(newId);
      }
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [messages.length, isFeedbackModalOpen]);

  // Smooth scroll when idle / initial load, non-blocking auto-scroll during token streaming
  useEffect(() => {
    if (messages.length === 0) return;

    if (!isLoading) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      return;
    }

    const isNearBottom =
      typeof window !== "undefined" &&
      window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160;

    if (isNearBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
    }
  }, [messages, isLoading]);

  const handleSend = async (queryText: string) => {
    const text = queryText.trim();
    if (!text || isLoading || Boolean(banState?.isBanned)) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsLoading(true);

    const assistantMsgId = (Date.now() + 1).toString();
    setActiveAssistantId(assistantMsgId);
    const initialTrace = buildDefaultTrace(text);

    const initialAssistantMessage: ChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      citations: [],
      trace: initialTrace,
      timestamp: new Date().toISOString(),
    };

    setMessages([...updatedMessages, initialAssistantMessage]);

    const historyPayload = updatedMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    let currentResponseText = "";
    let currentCitations: any[] = [];
    const startTime = Date.now();
    let rafId: number | null = null;

    const scheduleUpdate = () => {
      if (rafId !== null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? { ...msg, content: currentResponseText }
              : msg
          )
        );
      });
    };

    setQueueInfo(null);
    await streamChat(
      text,
      historyPayload,
      (token) => {
        setQueueInfo(null);
        currentResponseText += token;
        scheduleUpdate();
      },
      (citations) => {
        const seen = new Set<string>();
        const dedupedCitations: any[] = [];
        for (const cit of citations) {
          const key = cit.document_id ? `id_${cit.document_id}` : (cit.title || cit.resolution || "").trim().toLowerCase();
          if (!seen.has(key)) {
            seen.add(key);
            dedupedCitations.push(cit);
          }
        }
        currentCitations = dedupedCitations;
        const updatedSources = dedupedCitations.map((c) => {
          const rawUrl = c.pdf_url
            ? (c.pdf_url.startsWith("http") ? c.pdf_url : `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${c.pdf_url}`)
            : (c.document_id ? getDocumentPdfUrl(c.document_id) : undefined);
          return {
            name: `${c.resolution || c.title}${c.article ? ` (${c.article})` : ""}`,
            url: rawUrl,
          };
        });
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.id !== assistantMsgId) return msg;
            const updatedTrace: TraceNode[] = (msg.trace || initialTrace).map((node) => {
              if (node.type === "search" && updatedSources.length > 0) {
                return { ...node, sources: updatedSources };
              }
              return node;
            });
            return {
              ...msg,
              citations: currentCitations,
              trace: updatedTrace,
            };
          })
        );
      },
      () => {
        setQueueInfo(null);
        if (rafId !== null) {
          cancelAnimationFrame(rafId);
          rafId = null;
        }
        setIsLoading(false);
        setActiveAssistantId(null);
        const duration = Math.max(1, Math.round((Date.now() - startTime) / 1000));
        setMessages((finalMessages) => {
          const updated = finalMessages.map((msg) =>
            msg.id === assistantMsgId
              ? { ...msg, content: currentResponseText, durationSeconds: duration }
              : msg
          );
          saveStoredChatHistory(updated);
          return updated;
        });
      },
      (err) => {
        setQueueInfo(null);
        if (rafId !== null) {
          cancelAnimationFrame(rafId);
          rafId = null;
        }
        console.error("Stream error", err);
        setIsLoading(false);
        setActiveAssistantId(null);
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.id !== assistantMsgId) return msg;
            if (banState?.isBanned) {
              return {
                ...msg,
                content:
                  currentResponseText ||
                  "🚫 **Acceso Suspendido:** Has acumulado 3 infracciones por consultas fuera del ámbito académico. El acceso se encuentra suspendido temporalmente durante 24 horas.",
              };
            }
            return {
              ...msg,
              content:
                currentResponseText +
                "\n\n*(Hubo un inconveniente temporal conectando con el servidor. Por favor verifica que el backend esté en ejecución).*",
            };
          })
        );
      },
      (queueData) => {
        if (queueData.position > 0) {
          setQueueInfo(queueData);
        } else {
          setQueueInfo(null);
        }
      },
      (banData) => {
        setBanState({
          isBanned: true,
          remainingSeconds: banData.remaining_seconds,
          reason: banData.reason,
        });
      }
    );
  };

  const handleStartNewSession = () => {
    // Preserve active ban state across session resets
    clearStoredChatHistory();
    setMessages([]);
    if (typeof window !== "undefined") {
      const newId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
      sessionStorage.setItem("can_i_graduate_session_id", newId);
      setSessionId(newId);
      if (window.location.hash === "#chat") {
        window.history.replaceState(null, "", window.location.pathname);
      }
    }
  };


  const handleSubmitFeedback = async () => {
    if (!feedbackComments.trim()) return;
    setFeedbackSubmitting(true);
    setFeedbackError(null);
    try {
      const transcriptMessages = feedbackIncludeTranscript
        ? messages.map((m) => ({
            role: m.role,
            content: m.content,
            timestamp: m.timestamp,
            citations: m.citations?.map((c) => ({
              title: c.title,
              resolution: c.resolution,
              article: c.article,
            })),
          }))
        : undefined;

      const res = await sendSessionFeedback({
        session_id: sessionId,
        user_email: feedbackUserEmail.trim() || undefined,
        feedback_type: feedbackType,
        rating: feedbackRating || undefined,
        comments: feedbackComments.trim(),
        include_transcript: feedbackIncludeTranscript,
        messages: transcriptMessages,
      });

      setFeedbackEmailSent(res.email_sent || false);
      setFeedbackMailtoUrl(res.mailto_url || null);
      setFeedbackGmailUrl(res.gmail_compose_url || null);
      setFeedbackSuccess(true);
    } catch (err: any) {
      setFeedbackError(err.message || "Error al registrar retroalimentación");
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const renderSecurityBanBanner = () => {
    if (!banState?.isBanned) return null;
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: -10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -10 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="w-full my-3 z-30 select-none text-left"
      >
        <div className="relative overflow-hidden rounded-2xl border-2 border-red-500/80 bg-red-950/90 p-4 sm:p-5 backdrop-blur-2xl shadow-[0_0_50px_rgba(239,68,68,0.4)] text-white">
          {/* Ambient red glow */}
          <div className="absolute -top-12 -right-12 w-44 h-44 bg-red-500/25 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-12 -left-12 w-44 h-44 bg-red-600/20 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center gap-3.5 sm:gap-4">
            <div className="size-11 sm:size-12 rounded-2xl bg-red-600/30 border border-red-500/60 flex items-center justify-center text-xl sm:text-2xl shrink-0 shadow-[0_0_20px_rgba(239,68,68,0.5)]">
              🔒
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm sm:text-base font-bold text-red-100 tracking-tight flex items-center gap-2">
                  <span>Acceso Suspendido por 24 Horas</span>
                </h3>
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-black/70 border border-red-500/60 text-red-300 font-mono text-xs font-bold tabular-nums shadow-inner">
                  <span className="inline-block size-2 rounded-full bg-red-500 animate-pulse" />
                  <span>Tiempo restante: {formatCountdown(banState.remainingSeconds)}</span>
                </div>
              </div>
              <p className="mt-1.5 text-xs sm:text-[13px] text-red-200/90 leading-relaxed">
                Has acumulado 3 infracciones por consultas no relacionadas con la Universidad Distrital o normativas académicas.
                {banState.reason && (
                  <span className="block mt-1 font-mono text-xs text-red-300/80">
                    Motivo: {banState.reason}
                  </span>
                )}
              </p>
              <div className="mt-2.5 pt-2 border-t border-red-500/25 flex items-center gap-2 text-[11px] sm:text-xs text-red-300/75 font-medium">
                <span>🛡️ El envío de preguntas y selección de sugerencias están temporalmente deshabilitados durante la suspensión.</span>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    );
  };

  return (
    <div
      className={`relative bg-black text-neutral-100 font-sans selection:bg-amber-500/30 selection:text-amber-200 overflow-x-clip flex flex-col ${
        isHeroState ? "h-[100dvh] max-h-[100dvh] overflow-hidden overscroll-none" : "min-h-[100dvh]"
      }`}
    >
      {/* Ambient MoltenMetal WebGL Background (Full-viewport coverage) */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div
          style={{ width: "100%", height: "100%", position: "relative" }}
          className="pointer-events-auto opacity-90 transition-opacity duration-700"
        >
          <MoltenMetal
            color1="#ff6f00"
            color2="#ffb000"
            color3="#ffffff"
            speed={0.25}
            scale={6.3}
            detail={3}
            glow={1.9}
            coreSize={0.1}
            swirl={0.6}
            fold={-0.32}
            blackPoint={0.02}
            brightness={1.8}
            colorMode="ember"
            grain={true}
            grainIntensity={0.01}
            mouseInteraction={true}
            mouseStrength={0.1}
            opacity={1.0}
          />
          {/* Very light edge gradient to protect navbar and footer text contrast without darkening the view */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/40 pointer-events-none" />
        </div>
      </div>

      {/* Recessed Apple UI Chrome Navbar (Locked / Sticky top-0 for seamless chat scrolling) */}
      <header className="sticky top-0 z-40 h-16 border-b border-white/[0.08] bg-black/70 sm:bg-black/50 backdrop-blur-2xl px-4 sm:px-6 lg:px-8 flex items-center justify-between transition-all duration-300">
        <div className="flex items-center gap-2.5 sm:gap-3">
          <button
            onClick={handleStartNewSession}
            title="Volver al inicio - Can I Graduate UD"
            className="flex items-center focus:outline-none transition-transform duration-200 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <Image
              src="/images/logo-canigraduateud-header.png"
              alt="Can I Graduate UD"
              width={180}
              height={44}
              priority
              className="h-8 sm:h-9 md:h-10 w-auto object-contain drop-shadow-sm -translate-y-1 sm:-translate-y-1.5 md:-translate-y-2"
            />
          </button>
          <div className="flex items-center gap-1.5 sm:gap-2 select-none -translate-y-0.5 sm:-translate-y-1">
            <span className="h-2.5 sm:h-3 w-px bg-white/20" />
            <span className="text-[9px] sm:text-[11px] font-mono font-semibold tracking-[0.18em] sm:tracking-[0.22em] uppercase text-transparent bg-clip-text bg-gradient-to-r from-neutral-200 via-neutral-100 to-neutral-400 drop-shadow-sm">
              Beta
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          {messages.length > 0 && (
            <button
              onClick={handleStartNewSession}
              disabled={Boolean(banState?.isBanned)}
              title="Comenzar una nueva sesión y volver al menú principal"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-300 hover:text-amber-200 bg-amber-500/10 hover:bg-amber-500/20 px-3 py-1.5 rounded-full border border-amber-500/30 transition-all duration-200 active:scale-95 backdrop-blur-md cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden xs:inline sm:inline">Nueva sesión</span>
            </button>
          )}
          {messages.length > 0 && (
            <button
              onClick={() => {
                setFeedbackSuccess(false);
                setFeedbackError(null);
                setIsFeedbackModalOpen(true);
              }}
              title="Enviar feedback sobre esta sesión a canigraduateud@gmail.com"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-neutral-300 hover:text-white bg-white/[0.06] hover:bg-white/[0.12] px-3 py-1.5 rounded-full border border-white/15 transition-all duration-200 active:scale-95 backdrop-blur-md cursor-pointer"
            >
              <MessageSquareHeart className="w-3.5 h-3.5 text-amber-400/80" />
              <span className="hidden sm:inline">Feedback</span>
            </button>
          )}
          {messages.length === 0 && (
            <a
              href="https://github.com/Wallyway/CanIGraduateUD-RAG"
              target="_blank"
              rel="noopener noreferrer"
              title="Ver repositorio en GitHub (Código Abierto)"
              className="p-2 text-neutral-400 hover:text-white hover:bg-white/10 rounded-full transition-all active:scale-95 flex items-center justify-center cursor-pointer"
              aria-label="Repositorio de GitHub"
            >
              <Github className="w-4 h-4" />
            </a>
          )}
          <a
            href="https://www.udistrital.edu.co"
            target="_blank"
            rel="noopener noreferrer"
            title="Universidad Distrital Francisco José de Caldas"
            className="p-1 hover:opacity-85 transition-opacity duration-200 flex items-center justify-center shrink-0 cursor-pointer"
            aria-label="Portal Universidad Distrital"
          >
            <Image
              src="/images/logo-ud-header.png"
              alt="Logo Universidad Distrital"
              width={36}
              height={36}
              priority
              className="w-7 h-7 sm:w-8 sm:h-8 object-contain drop-shadow-sm transition-transform duration-200 hover:scale-105"
            />
          </a>
        </div>
      </header>

      {/* Main Viewport Content */}
      <main className={`relative z-10 flex-1 flex flex-col ${isHeroState ? "justify-center items-center overflow-hidden px-4 sm:px-6" : "justify-between"}`}>
        {isHeroState ? (
          /* Apple Centered Hero State (Chat in the middle of the viewport with title above) */
          <div className="w-full max-w-3xl flex flex-col items-center justify-center py-2 sm:py-4">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
              className="text-center mb-3 sm:mb-6 w-full"
            >

              {/* Title & Headline */}
              <h1 className="text-3xl sm:text-5xl md:text-6xl font-semibold tracking-tight text-white mb-2 sm:mb-2.5 flex items-center justify-center flex-wrap gap-x-2 sm:gap-x-3.5 leading-none">
                <span>Can I Graduate</span>
                <span className="inline-flex items-center shrink-0">
                  <Image
                    src="/images/ud-virrete.png"
                    alt="UD"
                    width={180}
                    height={135}
                    priority
                    className="h-10 sm:h-14 md:h-16 w-auto object-contain drop-shadow-sm select-none -translate-y-1.5 sm:-translate-y-2.5 md:-translate-y-3.5"
                  />
                  <span className="select-none ml-0.5 sm:ml-1">?</span>
                </span>
              </h1>
              <p className="text-xs sm:text-base text-neutral-400 max-w-md mx-auto leading-relaxed font-normal">
                Asistente RAG oficial para resolver tus requisitos, pasantías,
                inglés B2 y modalidades de grado en Ingeniería de Sistemas.
              </p>
            </motion.div>

            {/* Red Glassmorphism Security Banner (Active ban) */}
            {renderSecurityBanBanner()}

            {/* Centered Prompt Input Box */}
            <motion.div
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="w-full"
            >
              <div className={`rounded-3xl border bg-neutral-900/30 backdrop-blur-xl shadow-[0_12px_40px_rgba(0,0,0,0.3)] overflow-hidden transition-all duration-300 ${
                banState?.isBanned ? "border-red-500/50 opacity-80" : "border-white/15 hover:border-white/25"
              }`}>
                <PromptInputBox
                  onSend={(message) => handleSend(message)}
                  isLoading={isLoading}
                  disabled={isLoading || Boolean(banState?.isBanned)}
                  placeholder={
                    banState?.isBanned
                      ? "Acceso suspendido temporalmente por acumulación de strikes..."
                      : "Escribe tu consulta sobre modalidades, pasantías, paz y salvos..."
                  }
                  className="bg-transparent border-0 shadow-none text-white"
                />
              </div>
            </motion.div>

            {/* Quick Suggestion Chips */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="mt-3 sm:mt-5 w-full"
            >
              <div className="flex items-center justify-center gap-1.5 text-[11px] sm:text-xs text-neutral-400 mb-2 font-medium">
                <HelpCircle className="w-3.5 h-3.5 text-amber-400" />
                <span>Consultas frecuentes de estudiantes:</span>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-1.5 sm:gap-2">
                {SUGGESTIONS.map((sug, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(sug.full)}
                    disabled={isLoading || Boolean(banState?.isBanned)}
                    className={`text-[11.5px] sm:text-xs px-3 sm:px-4 py-1.5 sm:py-2 rounded-full border transition-all duration-200 shadow-sm backdrop-blur-md text-center ${
                      banState?.isBanned
                        ? "bg-red-950/20 text-neutral-500 border-red-500/20 opacity-40 cursor-not-allowed pointer-events-none"
                        : "bg-white/[0.04] hover:bg-white/[0.09] text-neutral-300 hover:text-white border-white/10 hover:border-white/20 active:scale-95 cursor-pointer"
                    }`}
                    title={sug.full}
                  >
                    <span className="sm:hidden">{sug.label}</span>
                    <span className="hidden sm:inline">{sug.full}</span>
                  </button>
                ))}
              </div>
            </motion.div>
          </div>
        ) : (
          /* Active Chat Thread */
          <div className="flex-1 flex flex-col justify-between max-w-3xl mx-auto w-full px-4 sm:px-6 py-4 sm:py-6">

            <div className="space-y-6 pb-6">
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, ease: "easeOut" }}
                    className={`flex flex-col ${
                      msg.role === "user" ? "items-end" : "items-start"
                    }`}
                  >
                    <div
                      className={`max-w-[90%] sm:max-w-[85%] rounded-3xl p-5 md:p-6 shadow-lg backdrop-blur-xl transition-all ${
                        msg.role === "user"
                          ? "bg-white/[0.08] text-white border border-white/15 rounded-tr-md shadow-[0_4px_20px_rgba(0,0,0,0.2)]"
                          : "bg-black/35 text-neutral-200 border border-white/10 rounded-tl-md shadow-[0_8px_32px_rgba(0,0,0,0.3)]"
                      }`}
                    >
                      {msg.role === "user" ? (
                        <div className="text-sm md:text-[15px] leading-relaxed text-white whitespace-pre-wrap select-text">
                          {msg.content}
                        </div>
                      ) : (
                        <div className="flex flex-col gap-2">
                          {/* Agent Thinking / Trace Component */}
                          <div className="pt-0.5 pb-1">
                            <ThinkingState
                              nodes={msg.trace || buildDefaultTrace(msg.content || "Consulta UD")}
                              isWorking={isLoading && msg.id === activeAssistantId && !msg.content}
                              autoPlay={isLoading && msg.id === activeAssistantId}
                              durationSeconds={msg.durationSeconds ?? 3}
                              workingLabel="Pensando y consultando normativa UD..."
                              settledLabel={(sec) => (
                                <span>
                                  Consultó normativa durante <span className="tabular-nums font-mono text-[12px]">{sec}</span> {sec === 1 ? "segundo" : "segundos"}
                                </span>
                              )}
                            />
                          </div>

                          {/* Virtual Waiting Queue Banner */}
                          {queueInfo && queueInfo.position > 0 && isLoading && msg.id === activeAssistantId && (
                            <div className="my-2 p-3.5 rounded-xl border border-amber-500/30 bg-amber-500/10 backdrop-blur-md flex items-center gap-3 animate-pulse shadow-[0_0_18px_rgba(245,158,11,0.15)] transition-all duration-300">
                              <span className="text-xl shrink-0">⏳</span>
                              <div className="text-xs sm:text-sm font-medium text-amber-200/90 leading-snug">
                                Alta afluencia de consultas. Estás en la posición{" "}
                                <span className="font-bold text-amber-300 tabular-nums">
                                  #{queueInfo.position}
                                </span>{" "}
                                de la fila (espera estimada: ~{queueInfo.estimated_seconds}s)...
                              </div>
                            </div>
                          )}

                          {/* Markdown Response Content or Active Waiting State */}
                          {msg.content ? (
                            <div className="max-w-none text-neutral-200 leading-relaxed text-sm md:text-base break-words font-normal pt-1.5 select-text">
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={STATIC_MARKDOWN_COMPONENTS}
                              >
                                {msg.content}
                              </ReactMarkdown>
                              {isLoading && msg.id === activeAssistantId && (
                                <span className="inline-block w-1.5 h-3.5 ml-1 bg-amber-400/90 rounded-xs animate-pulse align-middle" />
                              )}
                            </div>
                          ) : (
                            isLoading && msg.id === activeAssistantId && !queueInfo && (
                              <div className="flex items-center gap-2 pt-1 pb-0.5 text-xs text-neutral-400 font-mono">
                                <span className="w-1.5 h-3.5 bg-amber-400/90 rounded-xs animate-pulse inline-block" />
                                <span className="text-[12px] text-neutral-400">
                                  Preparando respuesta oficial...
                                </span>
                              </div>
                            )
                          )}

                          {/* Official Citations */}
                          {msg.citations && msg.citations.length > 0 && (
                            <div className="mt-3.5 pt-3.5 border-t border-white/[0.08]">
                              <div className="flex items-center gap-1.5 text-xs font-semibold text-neutral-400 mb-2.5">
                                <Sparkles className="w-3 h-3 text-amber-400" />
                                <span>Fuentes y Resoluciones citadas:</span>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {msg.citations.map((cit, idx) => (
                                  <CitationBadge key={idx} citation={cit} />
                                ))}
                              </div>
                            </div>
                          )}

                          {/* 1-Click Retry Action Button for Saturated/Timed Out Requests */}
                          {msg.content && !isLoading && (msg.content.includes("reintenta") || msg.content.includes("volumen muy alto")) && (
                            <div className="mt-2.5">
                              <button
                                onClick={() => {
                                  if (banState?.isBanned) return;
                                  const idx = messages.findIndex((m) => m.id === msg.id);
                                  const prevUserMsg = idx > 0 ? messages[idx - 1] : null;
                                  if (prevUserMsg && prevUserMsg.role === "user" && prevUserMsg.content) {
                                    handleSend(prevUserMsg.content);
                                  }
                                }}
                                disabled={Boolean(banState?.isBanned)}
                                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all shadow-sm ${
                                  banState?.isBanned
                                    ? "bg-red-950/20 text-neutral-500 border-red-500/20 opacity-40 cursor-not-allowed pointer-events-none"
                                    : "bg-amber-500/15 hover:bg-amber-500/25 border-amber-500/30 text-amber-300 active:scale-95 cursor-pointer"
                                }`}
                              >
                                <span>🔄</span>
                                <span>Reintentar consulta con 1 clic</span>
                              </button>
                            </div>
                          )}

                          {/* Feedback Action Link for this session/message */}
                          {msg.content && !isLoading && (
                            <div className="mt-3 pt-2.5 border-t border-white/[0.06] flex items-center justify-between text-[11px] text-neutral-400">
                              <button
                                onClick={() => {
                                  setFeedbackSuccess(false);
                                  setFeedbackError(null);
                                  setIsFeedbackModalOpen(true);
                                }}
                                className="inline-flex items-center gap-1.5 text-neutral-400 hover:text-amber-300 transition-colors py-0.5"
                                title="Enviar retroalimentación sobre esta respuesta a canigraduateud@gmail.com"
                              >
                                <MessageSquareHeart className="w-3.5 h-3.5 text-amber-400/80" />
                                <span>Enviar feedback de esta sesión</span>
                              </button>
                              <span className="text-[10px] text-neutral-500 font-mono hidden sm:inline">
                                canigraduateud@gmail.com
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              {isLoading && (!messages.length || messages[messages.length - 1]?.role !== "assistant") && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-start"
                >
                  <div className="bg-black/35 border border-white/10 rounded-3xl rounded-tl-md px-5 py-3.5 text-neutral-400 text-sm flex items-center gap-3 backdrop-blur-xl shadow-md">
                    <PixelDotsLoader />
                    <span className="text-xs text-neutral-400 font-mono">
                      Consultando normativa oficial UD...
                    </span>
                  </div>
                </motion.div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>
        )}
      </main>

      {/* Docked Prompt Bar for active chat mode */}
      {!isHeroState && (
        <footer className="sticky bottom-0 z-30 bg-transparent p-4 md:p-5 pointer-events-none">
          <div className="max-w-3xl mx-auto w-full pointer-events-auto">
            {renderSecurityBanBanner()}
            <div className={`rounded-3xl border bg-neutral-900/30 backdrop-blur-xl shadow-[0_12px_40px_rgba(0,0,0,0.3)] overflow-hidden transition-all duration-300 ${
              banState?.isBanned ? "border-red-500/50 opacity-80" : "border-white/15 hover:border-white/25"
            }`}>
              <PromptInputBox
                onSend={(message) => handleSend(message)}
                isLoading={isLoading}
                disabled={isLoading || Boolean(banState?.isBanned)}
                placeholder={
                  banState?.isBanned
                    ? "Acceso suspendido temporalmente por acumulación de strikes..."
                    : "Pregunta sobre modalidades, requisitos de grado, pasantía..."
                }
                className="bg-transparent border-0 shadow-none text-white"
              />
            </div>
            <p className="text-[11px] text-neutral-400/80 text-center mt-2 font-normal tracking-wide drop-shadow-sm">
              Información oficial de la Facultad de Ingeniería • Universidad Distrital Francisco José de Caldas
            </p>
          </div>
        </footer>
      )}

      {/* Feedback Modal */}
      <AnimatePresence>
        {isFeedbackModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-lg bg-neutral-900 border border-white/15 rounded-3xl p-6 sm:p-7 shadow-2xl space-y-5 text-neutral-200 relative overflow-hidden"
            >
              <button
                onClick={() => setIsFeedbackModalOpen(false)}
                className="absolute top-5 right-5 p-1.5 rounded-full text-neutral-400 hover:text-white hover:bg-white/10 transition"
              >
                <X className="w-4 h-4" />
              </button>

              {feedbackSuccess ? (
                <div className="text-center py-6 space-y-4">
                  <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center mx-auto">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">¡Gracias por tu retroalimentación!</h3>
                    <p className="text-xs sm:text-sm text-neutral-400 mt-1.5 max-w-sm mx-auto leading-relaxed">
                      {feedbackEmailSent ? (
                        <>
                          Tu reporte y la conversación han sido enviados automáticamente al correo{" "}
                          <span className="text-amber-300 font-mono font-medium">canigraduateud@gmail.com</span>.
                        </>
                      ) : (
                        <>
                          Tu reporte y transcripción quedaron guardados en el sistema para{" "}
                          <span className="text-amber-300 font-mono font-medium">canigraduateud@gmail.com</span>.
                        </>
                      )}
                    </p>
                  </div>

                  {!feedbackEmailSent && (feedbackGmailUrl || feedbackMailtoUrl) && (
                    <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-left space-y-3">
                      <div className="flex items-center gap-2 text-amber-300 text-xs font-semibold">
                        <Mail className="w-4 h-4" />
                        <span>Completar envío inmediato al correo:</span>
                      </div>
                      <p className="text-[11px] text-neutral-300 leading-relaxed">
                        Para enviar este reporte directamente a la bandeja de <strong>canigraduateud@gmail.com</strong> desde tu cuenta, pulsa abajo para abrir la plantilla con la conversación ya redactada:
                      </p>
                      <div className="flex flex-col sm:flex-row gap-2 pt-1">
                        {feedbackGmailUrl && (
                          <a
                            href={feedbackGmailUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#C2410C] hover:bg-[#EA580C] text-white font-semibold text-xs shadow-md transition active:scale-95 text-center"
                          >
                            <Mail className="w-3.5 h-3.5" />
                            <span>Enviar con Gmail Web</span>
                          </a>
                        )}
                        {feedbackMailtoUrl && (
                          <a
                            href={feedbackMailtoUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs border border-white/15 transition active:scale-95 text-center"
                          >
                            <span>App de Correo</span>
                          </a>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="pt-2">
                    <button
                      onClick={() => setIsFeedbackModalOpen(false)}
                      className="px-5 py-2 text-xs font-semibold rounded-xl bg-white/10 hover:bg-white/20 text-white transition"
                    >
                      Cerrar
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div>
                    <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold uppercase tracking-wider mb-1">
                      <MessageSquareHeart className="w-4 h-4" />
                      <span>Feedback de la Sesión</span>
                    </div>
                    <h3 className="text-lg font-bold text-white tracking-tight">
                      Envíanos tus comentarios
                    </h3>
                    <p className="text-xs text-neutral-400 mt-0.5">
                      Tus observaciones nos permiten auditar respuestas y mejorar la base normativa.
                      Destino: <span className="text-amber-300 font-mono font-medium">canigraduateud@gmail.com</span>
                    </p>
                  </div>

                  {/* Rating Stars */}
                  <div>
                    <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                      ¿Cómo calificarías las respuestas de esta sesión?
                    </label>
                    <div className="flex items-center gap-1.5">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setFeedbackRating(star)}
                          className="p-1 text-neutral-500 hover:text-amber-400 transition"
                        >
                          <Star
                            className={`w-5 h-5 ${
                              feedbackRating >= star
                                ? "text-amber-400 fill-amber-400"
                                : "text-neutral-600"
                            }`}
                          />
                        </button>
                      ))}
                      <span className="text-xs text-neutral-400 ml-2 font-medium">
                        {feedbackRating === 5 && "Excelente"}
                        {feedbackRating === 4 && "Buena"}
                        {feedbackRating === 3 && "Aceptable"}
                        {feedbackRating === 2 && "Regular"}
                        {feedbackRating === 1 && "Deficiente"}
                      </span>
                    </div>
                  </div>

                  {/* Category Pills */}
                  <div>
                    <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                      Tipo de observación:
                    </label>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                      {[
                        { id: "sugerencia", label: "💡 Sugerencia" },
                        { id: "informacion_imprecisa", label: "⚠️ Imprecisión" },
                        { id: "error_tecnico", label: "🐞 Error" },
                        { id: "general", label: "💬 General" },
                      ].map((cat) => (
                        <button
                          key={cat.id}
                          type="button"
                          onClick={() => setFeedbackType(cat.id as any)}
                          className={`text-xs px-2.5 py-1.5 rounded-xl border transition text-center ${
                            feedbackType === cat.id
                              ? "bg-amber-500/20 border-amber-400/80 text-amber-200 font-semibold"
                              : "bg-white/[0.04] border-white/10 text-neutral-400 hover:text-white"
                          }`}
                        >
                          {cat.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Comments */}
                  <div>
                    <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                      Comentarios u observaciones <span className="text-amber-400">*</span>
                    </label>
                    <textarea
                      rows={3}
                      value={feedbackComments}
                      onChange={(e) => setFeedbackComments(e.target.value)}
                      placeholder="¿Qué respuesta faltó, qué normativa no se citó o qué sugerencia tienes?"
                      className="w-full text-xs sm:text-sm bg-neutral-950/70 border border-white/10 rounded-2xl p-3 text-white placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-amber-500/40 focus:border-amber-400/60 resize-none"
                    />
                  </div>

                  {/* Contact Email (Optional) */}
                  <div>
                    <label className="block text-xs font-medium text-neutral-300 mb-1">
                      Correo de contacto (opcional):
                    </label>
                    <input
                      type="email"
                      value={feedbackUserEmail}
                      onChange={(e) => setFeedbackUserEmail(e.target.value)}
                      placeholder="tu.correo@udistrital.edu.co"
                      className="w-full text-xs bg-neutral-950/70 border border-white/10 rounded-xl px-3 py-2 text-white placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-amber-500/40 focus:border-amber-400/60"
                    />
                  </div>

                  {/* Checkbox: Attach Session Transcript */}
                  <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-3 flex items-start gap-3">
                    <input
                      type="checkbox"
                      id="attachTranscript"
                      checked={feedbackIncludeTranscript}
                      onChange={(e) => setFeedbackIncludeTranscript(e.target.checked)}
                      className="mt-0.5 rounded border-white/20 bg-neutral-800 text-amber-500 focus:ring-amber-500 focus:ring-offset-neutral-900 cursor-pointer"
                    />
                    <label htmlFor="attachTranscript" className="text-xs cursor-pointer select-none">
                      <span className="font-semibold text-white block">
                        Adjuntar conversación de esta sesión ({messages.length} mensaje{messages.length === 1 ? "" : "s"})
                      </span>
                      <span className="text-neutral-400 block mt-0.5 text-[11px] leading-relaxed">
                        Permite al equipo analizar las preguntas y respuestas de esta sesión en concreto para auditar la precisión.
                      </span>
                    </label>
                  </div>

                  {feedbackError && (
                    <p className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 p-2.5 rounded-xl">
                      {feedbackError}
                    </p>
                  )}

                  {/* Actions */}
                  <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-white/10">
                    <button
                      type="button"
                      onClick={() => setIsFeedbackModalOpen(false)}
                      className="px-4 py-2 text-xs font-medium text-neutral-400 hover:text-white transition"
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      disabled={feedbackSubmitting || !feedbackComments.trim()}
                      onClick={handleSubmitFeedback}
                      className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-black shadow-md transition disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
                    >
                      {feedbackSubmitting ? (
                        <span>Enviando...</span>
                      ) : (
                        <>
                          <Send className="w-3.5 h-3.5" />
                          <span>Enviar a canigraduateud@gmail.com</span>
                        </>
                      )}
                    </button>
                  </div>
                </>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ChatInterface;
