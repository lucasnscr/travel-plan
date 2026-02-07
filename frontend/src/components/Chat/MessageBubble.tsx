import { memo, type ComponentPropsWithoutRef } from "react";
import { motion } from "framer-motion";
import Markdown from "react-markdown";
import { Bot, User } from "lucide-react";
import { RichResponse } from "./RichResponse";
import { cn } from "@/utils/cn";
import type { ChatMessage } from "@/stores/chat-store";

/* ------------------------------------------------------------------ */
/*  Relative timestamp                                                 */
/* ------------------------------------------------------------------ */

function relativeTime(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 10) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(ts).toLocaleDateString();
}

/* ------------------------------------------------------------------ */
/*  Markdown component overrides for dark theme                        */
/* ------------------------------------------------------------------ */

const markdownComponents: ComponentPropsWithoutRef<typeof Markdown>["components"] = {
  p: ({ children }) => (
    <p className="mb-2 last:mb-0 text-[13px] leading-relaxed text-slate-300">
      {children}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-slate-100">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="text-slate-400">{children}</em>
  ),
  code: ({ children, className }) => {
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return (
        <code className="block overflow-x-auto rounded-lg bg-white/5 p-3 text-[12px] text-brand-300 font-mono">
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-brand-500/15 px-1 py-0.5 text-[12px] text-brand-400 font-mono">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-hidden rounded-lg border border-white/5">
      {children}
    </pre>
  ),
  ul: ({ children }) => (
    <ul className="mb-2 ml-4 list-disc space-y-0.5 text-[13px] text-slate-300">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 ml-4 list-decimal space-y-0.5 text-[13px] text-slate-300">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="text-[13px] leading-relaxed">{children}</li>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-brand-500/40 pl-3 text-[13px] text-slate-400 italic">
      {children}
    </blockquote>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-brand-400 underline underline-offset-2 hover:text-brand-300"
    >
      {children}
    </a>
  ),
  h1: ({ children }) => (
    <h1 className="mb-2 text-sm font-bold text-slate-100">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-1.5 text-sm font-semibold text-slate-100">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1 text-[13px] font-semibold text-slate-200">{children}</h3>
  ),
  hr: () => <hr className="my-3 border-white/10" />,
};

/* ------------------------------------------------------------------ */
/*  MessageBubble                                                      */
/* ------------------------------------------------------------------ */

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble = memo(function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "flex gap-2.5 px-1",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-brand-500/20" : "bg-white/5",
        )}
      >
        {isUser ? (
          <User className="h-3.5 w-3.5 text-brand-400" />
        ) : (
          <Bot className="h-3.5 w-3.5 text-slate-400" />
        )}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "min-w-0 max-w-[85%] space-y-1",
          isUser ? "items-end" : "items-start",
        )}
      >
        <div
          className={cn(
            "rounded-2xl border px-3.5 py-2.5",
            isUser
              ? "rounded-br-md border-brand-500/30 bg-brand-500/15"
              : "rounded-bl-md border-white/10 bg-white/[0.04]",
          )}
        >
          {/* Content */}
          {isUser ? (
            <p className="text-[13px] leading-relaxed text-slate-100">
              {message.content}
            </p>
          ) : (
            <div className="prose-dark">
              <Markdown components={markdownComponents}>
                {message.content}
              </Markdown>
              {message.isStreaming && message.content.length > 0 && (
                <span className="inline-block h-4 w-0.5 animate-pulse bg-slate-400 align-text-bottom" />
              )}
            </div>
          )}
        </div>

        {/* Rich response attachments */}
        {!isUser && message.attachments && message.attachments.length > 0 && !message.isStreaming && (
          <RichResponse attachments={message.attachments} />
        )}

        {/* Timestamp */}
        <p
          className={cn(
            "px-1 text-[10px] text-slate-600",
            isUser ? "text-right" : "text-left",
          )}
        >
          {relativeTime(message.timestamp)}
        </p>
      </div>
    </motion.div>
  );
});
