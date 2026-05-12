import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as echarts from "echarts";
import api from "../api/client";

// ---------------------------------------------------------------------------
// EChart — raw echarts with resize observer
// ---------------------------------------------------------------------------

function EChart({ option }: { option: object }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    chartRef.current = echarts.init(containerRef.current, null, { renderer: "canvas" });
    const obs = new ResizeObserver(() => chartRef.current?.resize());
    obs.observe(containerRef.current);
    return () => {
      obs.disconnect();
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;
    try {
      chartRef.current.setOption({ backgroundColor: "transparent", ...option }, true);
    } catch {
      // malformed LLM option — silently ignore
    }
  }, [option]);

  return <div ref={containerRef} style={{ height: 300, width: "100%" }} />;
}

// ---------------------------------------------------------------------------
// Simple markdown renderer (bold, code, bullet lists)
// ---------------------------------------------------------------------------

function MarkdownText({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) {
      if (elements.length > 0) elements.push(<div key={`gap-${i}`} className="h-2" />);
      continue;
    }

    const renderInline = (str: string) =>
      str.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((p, j) => {
        if (p.startsWith("**") && p.endsWith("**"))
          return <strong key={j} className="font-semibold text-slate-100">{p.slice(2, -2)}</strong>;
        if (p.startsWith("`") && p.endsWith("`"))
          return <code key={j} className="text-xs font-mono bg-slate-700/60 px-1.5 py-0.5 rounded text-violet-300">{p.slice(1, -1)}</code>;
        return <span key={j}>{p}</span>;
      });

    if (/^[-•*]\s/.test(line)) {
      elements.push(
        <div key={i} className="flex gap-2 items-start">
          <span className="text-violet-500 shrink-0 mt-px">·</span>
          <span className="leading-relaxed">{renderInline(line.replace(/^[-•*]\s/, ""))}</span>
        </div>
      );
    } else if (/^#{1,3}\s/.test(line)) {
      elements.push(
        <p key={i} className="font-semibold text-slate-100 text-sm">{renderInline(line.replace(/^#{1,3}\s/, ""))}</p>
      );
    } else {
      elements.push(<p key={i} className="leading-relaxed">{renderInline(line)}</p>);
    }
  }

  return <div className="space-y-1.5 text-sm text-slate-300">{elements}</div>;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Message {
  role: "user" | "assistant";
  content: string;
  chart?: object | null;
}

// ---------------------------------------------------------------------------
// Avatars
// ---------------------------------------------------------------------------

function ProwlAvatar() {
  return (
    <div className="w-7 h-7 rounded-lg bg-violet-600 flex items-center justify-center shrink-0">
      <svg viewBox="0 0 48 48" className="w-4 h-4" fill="none">
        <g stroke="white" strokeLinecap="round">
          <circle cx="10" cy="38" r="2.5" fill="white" stroke="none" />
          <path d="M 20,38 A 10,10 0 0 1 10,28" strokeWidth="3" />
          <path d="M 30,38 A 20,20 0 0 1 10,18" strokeWidth="3" />
          <path d="M 40,38 A 30,30 0 0 1 10,8" strokeWidth="3" />
        </g>
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ msg }: { msg: Message }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[88%] sm:max-w-[75%] bg-slate-800 rounded-2xl rounded-tr-sm px-4 py-3 text-sm text-slate-100 leading-relaxed">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-2.5 sm:gap-3 items-start">
      <ProwlAvatar />
      <div className="flex-1 min-w-0 pt-0.5 space-y-3 sm:space-y-4">
        <MarkdownText text={msg.content} />
        {msg.chart && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 sm:p-4 overflow-hidden">
            <EChart option={msg.chart} />
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Typing indicator
// ---------------------------------------------------------------------------

function TypingIndicator() {
  return (
    <div className="flex gap-3 items-start">
      <ProwlAvatar />
      <div className="pt-2.5">
        <div className="flex gap-1.5 items-center">
          {[0, 160, 320].map(delay => (
            <span
              key={delay}
              className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Suggestion cards
// ---------------------------------------------------------------------------

const SUGGESTIONS = [
  { label: "Score distribution", q: "Show me the score distribution as a chart" },
  { label: "Top companies", q: "Which companies have the most job matches?" },
  { label: "Application funnel", q: "Show my application status breakdown with a chart" },
  { label: "Scraping trends", q: "How has scraping activity trended across recent runs?" },
  { label: "Match rate", q: "What percentage of scraped jobs match my profile?" },
  { label: "Best match companies", q: "Which companies have the highest match rates?" },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function InsightsPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: summary } = useQuery<{ total_listings: number; apply_count: number }>({
    queryKey: ["insights-summary"],
    queryFn: () => api.get("/insights/summary").then(r => r.data),
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const history = messages.map(m => ({ role: m.role, content: m.content }));
    setMessages(prev => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);

    try {
      const res = await api.post("/insights/chat", { message: trimmed, history });
      setMessages(prev => [
        ...prev,
        { role: "assistant", content: res.data.text ?? "", chart: res.data.chart ?? null },
      ]);
    } catch {
      setMessages(prev => [
        ...prev,
        { role: "assistant", content: "Something went wrong. Please try again.", chart: null },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-[calc(100dvh-5.5rem)] md:h-[calc(100dvh-3rem)] w-full">
      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="max-w-3xl mx-auto px-4 sm:px-5 py-4 sm:py-6">

          {isEmpty ? (
            /* Empty / welcome state */
            <div className="flex flex-col items-center justify-center min-h-[45vh] sm:min-h-[55vh] gap-6 sm:gap-10 text-center">
              <div className="space-y-2 sm:space-y-3">
                <div className="w-12 h-12 sm:w-16 sm:h-16 rounded-2xl bg-violet-600/15 border border-violet-500/20 flex items-center justify-center mx-auto">
                  <svg className="w-6 h-6 sm:w-8 sm:h-8 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6.75v6.75" />
                  </svg>
                </div>
                <h2 className="text-lg sm:text-xl font-semibold text-slate-100">What would you like to know?</h2>
                <p className="text-sm text-slate-500 max-w-xs mx-auto">
                  Ask anything about your job search.{" "}
                  {summary && (
                    <span className="text-slate-600">
                      {summary.total_listings} listings · {summary.apply_count} matches
                    </span>
                  )}
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full">
                {SUGGESTIONS.map(s => (
                  <button
                    key={s.q}
                    onClick={() => send(s.q)}
                    className="text-left px-3 py-2.5 sm:px-4 sm:py-3.5 rounded-xl border border-slate-800 bg-slate-900/40 hover:border-violet-500/30 hover:bg-slate-800/60 text-sm text-slate-400 hover:text-slate-200 transition-all group"
                  >
                    <span className="font-medium group-hover:text-slate-300 block mb-0.5 text-[10px] sm:text-xs uppercase tracking-wide text-slate-500">
                      {s.label}
                    </span>
                    <span className="text-xs sm:text-sm">{s.q}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Chat messages */
            <div className="space-y-5 sm:space-y-8">
              {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
              {loading && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          )}

          {isEmpty && <div ref={bottomRef} />}
        </div>
      </div>

      {/* ── Input bar ── */}
      <div className="shrink-0 border-t border-slate-800/60 bg-slate-950/80 backdrop-blur-sm pt-3 pb-3 sm:pt-4 sm:pb-3">
        <div className="max-w-3xl mx-auto px-4 sm:px-5">
          <form onSubmit={e => { e.preventDefault(); send(input); }}>
            <div className="flex items-center gap-2 sm:gap-3 bg-slate-800/60 border border-slate-700 hover:border-slate-600 focus-within:border-violet-500/60 rounded-2xl transition-colors px-3 sm:px-4 py-2">
              <textarea
                ref={inputRef as unknown as React.RefObject<HTMLTextAreaElement>}
                value={input}
                onChange={e => {
                  setInput(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
                }}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }
                }}
                placeholder="Ask about your job data…"
                disabled={loading}
                rows={1}
                className="flex-1 bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none resize-none leading-5 p-0 m-0 border-0"
                style={{ maxHeight: 160 }}
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="shrink-0 w-8 h-8 flex items-center justify-center rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-slate-700 disabled:opacity-40 transition-colors"
              >
                <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.269 20.876L5.999 12zm0 0h7.5" />
                </svg>
              </button>
            </div>
          </form>
          <p className="hidden sm:block text-center text-xs text-slate-700 mt-2">Shift+Enter for new line · Enter to send</p>
        </div>
      </div>
    </div>
  );
}
