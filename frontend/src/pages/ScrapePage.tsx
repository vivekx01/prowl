import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { type Company, type ScrapeRun, type RunLog } from "../api/client";
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

const LOG_STYLES: Record<string, string> = {
  success: "text-emerald-400",
  error:   "text-red-400",
  warning: "text-amber-400",
  info:    "text-slate-400",
};

function LogPanel({ runId, running }: { runId: number; running: boolean }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: logs = [] } = useQuery<RunLog[]>({
    queryKey: ["run-logs", runId],
    queryFn: () => api.get(`/runs/${runId}/logs`).then(r => r.data),
    refetchInterval: running ? 1500 : false,
    staleTime: 0,
    enabled: runId > 0,
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  if (!logs.length && !running) return null;

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800 bg-slate-900/80">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-widest">Logs</span>
        {running && (
          <span className="flex items-center gap-1.5 text-xs text-violet-400">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            Running
          </span>
        )}
      </div>
      <div className="p-4 max-h-80 overflow-y-auto font-mono text-xs leading-5 space-y-0.5">
        {logs.map(l => (
          <div key={l.id} className={LOG_STYLES[l.level] ?? LOG_STYLES.info}>
            {l.message || " "}
          </div>
        ))}
        <div ref={bottomRef} />
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
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className={`badge border ${STATUS_STYLES[run.status] ?? STATUS_STYLES.pending}`}>
            {run.status}
          </span>
          <span className="text-sm text-slate-300">Run #{run.id}</span>
          {run.started_at && (
            <span className="text-xs text-slate-600">
              {new Date(run.started_at).toLocaleString()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          {(run.status === "running" || run.status === "completed") && (
            <span className="text-xs text-slate-500">
              {run.companies_done}/{run.companies_total} companies
            </span>
          )}
          {run.apply_count > 0 && (
            <span className="text-xs text-emerald-400 font-medium">
              {run.apply_count} matches
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
  const [maxAge, setMaxAge] = useState("");
  const [activeRunId, setActiveRunId] = useState<number>(0);

  const { data: companies = [] } = useQuery<Company[]>({
    queryKey: ["companies"],
    queryFn: () => api.get("/companies").then(r => r.data),
  });

  const { data: settings = [] } = useQuery<{ key: string; value: string }[]>({
    queryKey: ["settings"],
    queryFn: () => api.get("/settings").then(r => r.data),
  });

  const { data: runs = [], refetch: refetchRuns } = useQuery<ScrapeRun[]>({
    queryKey: ["runs"],
    queryFn: () => api.get("/runs").then(r => r.data),
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (maxAge === "") {
      const s = settings.find(s => s.key === "max_job_age_days");
      if (s) setMaxAge(s.value);
    }
  }, [settings]);

  // Auto-select the latest running run
  useEffect(() => {
    const running = runs.find(r => r.status === "running" || r.status === "pending");
    if (running && !activeRunId) setActiveRunId(running.id);
  }, [runs]);

  const activeRun = runs.find(r => r.id === activeRunId);
  const isRunning = !!runs.find(r => r.status === "running" || r.status === "pending");

  const startRun = useMutation({
    mutationFn: async () => {
      if (maxAge) {
        const s = settings.find(s => s.key === "max_job_age_days");
        if (maxAge !== s?.value) await api.put("/settings/max_job_age_days", { value: maxAge });
      }
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

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-widest">Max job age (days)</label>
          <div className="flex items-center gap-3">
            <input
              type="number"
              min={1}
              max={90}
              value={maxAge}
              onChange={e => setMaxAge(e.target.value)}
              className="input w-24"
            />
            <span className="text-xs text-slate-600">
              Listings older than this are skipped before any LLM call
            </span>
          </div>
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
            <LogPanel key={activeRunId} runId={activeRunId} running={activeRun?.status === "running"} />
          )}
        </div>
      )}
    </div>
  );
}
