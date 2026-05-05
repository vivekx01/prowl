import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { type Company, type ScrapeRun } from "../api/client";
import { IconChevronDown } from "../components/Icons";

// ---------------------------------------------------------------------------
// Company multi-select
// ---------------------------------------------------------------------------

function CompanySelector({
  companies,
  selected,
  onChange,
}: {
  companies: Company[];
  selected: Set<number>;
  onChange: (s: Set<number>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fn = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);

  const filtered = companies.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  function toggle(id: number) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    if (next.size === companies.length) onChange(new Set());
    else onChange(next);
  }

  const label =
    selected.size === 0
      ? `All companies (${companies.length})`
      : `${selected.size} of ${companies.length} selected`;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full input flex items-center justify-between gap-2 text-left"
      >
        <span className={selected.size === 0 ? "text-slate-400" : "text-slate-100"}>
          {label}
        </span>
        <IconChevronDown className={`w-4 h-4 text-slate-500 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute z-20 mt-1 w-full card shadow-2xl overflow-hidden">
          <div className="p-2 border-b border-slate-800">
            <input
              autoFocus
              type="text"
              placeholder="Search…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="input text-xs py-1.5"
            />
          </div>
          <div className="max-h-56 overflow-y-auto">
            <label className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-800/60 cursor-pointer border-b border-slate-800/40">
              <input
                type="checkbox"
                checked={selected.size === 0}
                onChange={() => onChange(new Set())}
                className="accent-violet-500 w-4 h-4"
              />
              <span className="text-sm text-slate-200 font-medium">All companies</span>
            </label>
            {filtered.map(c => (
              <label key={c.id} className="flex items-center gap-3 px-4 py-2 hover:bg-slate-800/60 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.has(c.id)}
                  onChange={() => toggle(c.id)}
                  className="accent-violet-500 w-4 h-4 shrink-0"
                />
                <span className="text-sm text-slate-300 truncate">{c.name}</span>
                <span className="ml-auto text-xs text-slate-600 shrink-0 capitalize">{c.platform}</span>
              </label>
            ))}
            {filtered.length === 0 && (
              <p className="px-4 py-3 text-sm text-slate-500">No companies match</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Log panel
// ---------------------------------------------------------------------------

const LOG_LEVEL: Record<string, { badge: string; text: string }> = {
  error:   { badge: "text-red-400 bg-red-400/10 border-red-400/20",             text: "text-red-300" },
  warning: { badge: "text-amber-400 bg-amber-400/10 border-amber-400/20",       text: "text-amber-200" },
  success: { badge: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20", text: "text-slate-200" },
  info:    { badge: "text-slate-400 bg-slate-700/40 border-slate-600/30",        text: "text-slate-400" },
};

interface LogEntry { id: number; timestamp: string; level: string; message: string; }

function LogPanel({ runId, running }: { runId: number; running: boolean }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastIdRef = useRef(0);

  useEffect(() => {
    setLogs([]);
    lastIdRef.current = 0;
  }, [runId]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await api.get(`/runs/${runId}/logs`, {
          params: { after_id: lastIdRef.current },
        });
        if (cancelled || !res.data.length) return;
        lastIdRef.current = res.data[res.data.length - 1].id;
        setLogs(prev => [...prev, ...res.data]);
      } catch {}
    };
    poll();
    if (!running) return;
    const t = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(t); };
  }, [runId, running]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800 bg-slate-900/80">
        <div className="flex items-center gap-2">
          {running ? (
            <span className="flex items-center gap-1.5 text-xs text-violet-400">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
              Live
            </span>
          ) : (
            <span className="text-xs text-slate-500">Logs</span>
          )}
        </div>
        <span className="text-xs text-slate-600">{logs.length} entr{logs.length === 1 ? "y" : "ies"}</span>
      </div>

      <div ref={scrollRef} className="max-h-80 overflow-y-auto bg-slate-900/60">
        {logs.length === 0 ? (
          <div className="flex items-center justify-center py-10">
            {running
              ? <span className="text-xs text-slate-600 animate-pulse">Waiting for logs…</span>
              : <span className="text-xs text-slate-700">No logs recorded</span>}
          </div>
        ) : (
          <div className="divide-y divide-slate-800/50">
            {logs.map(l => {
              const style = LOG_LEVEL[l.level] ?? LOG_LEVEL.info;
              return (
                <div
                  key={l.id}
                  className="flex items-start gap-3 px-4 py-2.5 hover:bg-slate-800/30 transition-colors"
                >
                  <span className="text-[10px] text-slate-600 tabular-nums shrink-0 pt-0.5 leading-4 min-w-[64px]">
                    {new Date(l.timestamp).toLocaleTimeString([], {
                      hour: "2-digit", minute: "2-digit", second: "2-digit",
                    })}
                  </span>
                  <span className={`shrink-0 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border leading-3 pt-[3px] min-w-[44px] text-center ${style.badge}`}>
                    {l.level}
                  </span>
                  <span className={`text-xs leading-snug break-words flex-1 min-w-0 font-mono ${style.text}`}>
                    {l.message || " "}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Run history row
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<string, string> = {
  completed:  "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  running:    "bg-violet-500/10 text-violet-400 border-violet-500/20",
  pending:    "bg-slate-500/10 text-slate-400 border-slate-600/20",
  failed:     "bg-red-500/10 text-red-400 border-red-500/20",
  cancelled:  "bg-orange-500/10 text-orange-400 border-orange-500/20",
};

function RunRow({
  run,
  onResume,
  active,
  onClick,
}: {
  run: ScrapeRun;
  onResume: (id: number) => void;
  active: boolean;
  onClick: () => void;
}) {
  const progress =
    run.companies_total > 0
      ? Math.round((run.companies_done / run.companies_total) * 100)
      : 0;

  return (
    <div
      onClick={onClick}
      className={`card p-4 cursor-pointer transition-colors hover:border-slate-700 ${active ? "border-violet-500/40" : ""}`}
    >
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
          <span className={`badge border ${STATUS_STYLES[run.status] ?? STATUS_STYLES.pending}`}>
            {run.status}
          </span>
          <span className="text-sm text-slate-300">Run #{run.id}</span>
          {run.started_at && (
            <span className="text-xs text-slate-600 hidden sm:inline">
              {new Date(run.started_at).toLocaleString()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 sm:gap-4 flex-wrap justify-end">
          {(run.status === "running" || run.status === "completed") && (
            <span className="text-xs text-slate-500">
              {run.companies_done}/{run.companies_total} co.
            </span>
          )}
          {run.new_listings > 0 && (
            <span className="text-xs text-violet-400 font-medium">
              +{run.new_listings}
            </span>
          )}
          {(run.status === "failed" || run.status === "cancelled") && (
            <button
              onClick={e => { e.stopPropagation(); onResume(run.id); }}
              className="text-xs text-amber-400 hover:text-amber-300 transition-colors border border-amber-500/30 px-2 py-0.5 rounded"
            >
              Resume
            </button>
          )}
        </div>
      </div>

      {run.status === "running" && run.companies_total > 0 && (
        <div className="mt-3 h-1 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-violet-500 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ScrapePage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [activeRunId, setActiveRunId] = useState<number>(0);

  const { data: companies = [] } = useQuery<Company[]>({
    queryKey: ["companies"],
    queryFn: () => api.get("/companies").then(r => r.data),
  });

  const { data: runs = [], refetch: refetchRuns } = useQuery<ScrapeRun[]>({
    queryKey: ["runs"],
    queryFn: () => api.get("/runs").then(r => r.data),
    refetchInterval: 5000,
  });

  // Auto-select the latest running run
  useEffect(() => {
    const running = runs.find(r => r.status === "running" || r.status === "pending");
    if (running && !activeRunId) setActiveRunId(running.id);
  }, [runs]);

  const activeRun = runs.find(r => r.id === activeRunId);
  const isRunning = !!runs.find(r => r.status === "running" || r.status === "pending");

  const startRun = useMutation({
    mutationFn: async () => {
      const company_ids = selected.size > 0 ? Array.from(selected) : null;
      return api.post("/scraper/run", { company_ids }).then(r => r.data);
    },
    onSuccess: (data) => {
      setActiveRunId(data.run_id);
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  const resumeRun = useMutation({
    mutationFn: (runId: number) => api.post(`/scraper/resume/${runId}`).then(r => r.data),
    onSuccess: (data) => {
      setActiveRunId(data.run_id);
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  const stopRun = useMutation({
    mutationFn: (runId: number) => api.post(`/scraper/stop/${runId}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });

  const activeOnly = companies.filter(c => c.active);

  return (
    <div className="w-full space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Scrape</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Configure and trigger scrape runs across your company list.
        </p>
      </div>

      {/* Controls */}
      <div className="card p-5 space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-widest">Companies</label>
          <CompanySelector companies={activeOnly} selected={selected} onChange={setSelected} />
        </div>


        <div className="flex items-center justify-between pt-1 border-t border-slate-800">
          <span className="text-xs text-slate-600">
            {isRunning ? (
              <span className="text-violet-400 font-medium">Scrape in progress…</span>
            ) : runs[0] ? (
              `Last run ${new Date(runs[0].started_at!).toLocaleString()}`
            ) : "No runs yet"}
          </span>
          <div className="flex items-center gap-2">
            {isRunning && (() => {
              const activeRun = runs.find(r => r.status === "running" || r.status === "pending");
              return activeRun ? (
                <button
                  onClick={() => { if (confirm("Stop the current scrape?")) stopRun.mutate(activeRun.id); }}
                  disabled={stopRun.isPending}
                  className="btn-ghost text-red-400 hover:text-red-300 border border-red-500/30 hover:border-red-400/50"
                >
                  {stopRun.isPending ? "Stopping…" : "Stop"}
                </button>
              ) : null;
            })()}
            <button
              onClick={() => startRun.mutate()}
              disabled={isRunning || startRun.isPending}
              className="btn-primary"
            >
              {isRunning ? "Running…" : "Run Scrape"}
            </button>
          </div>
        </div>
      </div>

      {/* Run history + live log side by side */}
      {(runs.length > 0 || activeRunId > 0) && (
        <div className={`grid gap-5 items-start ${activeRunId > 0 && runs.length > 0 ? "xl:grid-cols-2" : ""}`}>
          {runs.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-xs font-medium text-slate-500 uppercase tracking-widest px-1">
                Run history
              </h2>
              <div className="space-y-2 max-h-[28rem] overflow-y-auto pr-1">
                {runs.map(run => (
                  <RunRow
                    key={run.id}
                    run={run}
                    active={run.id === activeRunId}
                    onClick={() => setActiveRunId(run.id)}
                    onResume={id => resumeRun.mutate(id)}
                  />
                ))}
              </div>
            </div>
          )}

          {activeRunId > 0 && (
            <div className="space-y-2">
              <h2 className="text-xs font-medium text-slate-500 uppercase tracking-widest px-1">
                Run logs
              </h2>
              <LogPanel key={activeRunId} runId={activeRunId} running={activeRun?.status === "running"} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
