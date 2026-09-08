"use client";

import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export const MARKDOWN_COMPONENTS = {
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
  li: ({ children }: any) => (
    <li className="flex items-start gap-2.5 text-[14px] sm:text-[14.5px] leading-relaxed text-neutral-200/90">
      <span className="size-1.5 rounded-full bg-amber-400 mt-2 shrink-0 shadow-[0_0_8px_rgba(251,191,36,0.6)]" />
      <span className="flex-1">{children}</span>
    </li>
  ),
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

interface SmoothMarkdownProps {
  content: string;
  isStreaming: boolean;
}

export const SmoothMarkdown: React.FC<SmoothMarkdownProps> = ({
  content,
  isStreaming,
}) => {
  const [displayedLength, setDisplayedLength] = useState(isStreaming ? 0 : content.length);
  const targetLength = content.length;
  const displayedLengthRef = useRef(displayedLength);
  displayedLengthRef.current = displayedLength;

  useEffect(() => {
    if (!isStreaming) {
      setDisplayedLength(targetLength);
      return;
    }

    if (displayedLengthRef.current >= targetLength) return;

    let animId: number;
    let lastTime = performance.now();

    const tick = (currentTime: number) => {
      const delta = currentTime - lastTime;
      // 60 FPS tick (~16ms)
      if (delta >= 16) {
        lastTime = currentTime;
        const current = displayedLengthRef.current;
        const remaining = targetLength - current;

        if (remaining > 0) {
          // Dynamic step: fluid character flow without bursting
          const increment =
            remaining > 80
              ? Math.ceil(remaining / 6)
              : remaining > 30
              ? 4
              : remaining > 10
              ? 2
              : 1;
          const nextVal = Math.min(targetLength, current + increment);
          setDisplayedLength(nextVal);
          displayedLengthRef.current = nextVal;
        }
      }

      if (displayedLengthRef.current < targetLength) {
        animId = requestAnimationFrame(tick);
      }
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [content, isStreaming, targetLength]);

  const textToRender = isStreaming ? content.slice(0, displayedLength) : content;

  return (
    <div className="max-w-none text-neutral-200 leading-relaxed text-sm md:text-base break-words font-normal pt-1.5 select-text animate-[agent-fade_300ms_ease-out_both]">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
        {textToRender}
      </ReactMarkdown>
      {isStreaming && (
        <span className="inline-flex items-center ml-1.5 align-middle">
          <span className="size-2 rounded-full bg-amber-400 animate-ping inline-block opacity-75" />
          <span className="size-2 rounded-full bg-amber-400 inline-block -ml-2 shadow-[0_0_8px_rgba(251,191,36,0.9)]" />
        </span>
      )}
    </div>
  );
};

export default SmoothMarkdown;
