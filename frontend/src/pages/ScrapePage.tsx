import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { type Company, type ScrapeRun } from "../api/client";
import { IconChevronDown } from "../components/Icons";
import { ISTTimePicker, utcToIst } from "../components/ISTTimePicker";
import cronstrue from "cronstrue";

// ---------------------------------------------------------------------------
// Schedule card (global scrape schedule — interval or specific times)
// ---------------------------------------------------------------------------

const SCRAPE_PRESETS = [
  { label: "Every 10 min",   cron: "*/10 * * * *"  },
  { label: "Every 30 min",   cron: "*/30 * * * *"  },
  { label: "Every hour",     cron: "0 * * * *"     },
  { label: "Every 2 hours",  cron: "0 */2 * * *"   },
  { label: "Every 6 hours",  cron: "0 */6 * * *"   },
  { label: "Every 12 hours", cron: "0 */12 * * *"  },
  { label: "Daily",          cron: "0 0 * * *"     },
];

function cronDescription(expr: string): { text: string; error: boolean } {
  if (!expr.trim()) return { text: "No schedule — runs manually only", error: false };
  try {
    return { text: cronstrue.toString(expr, { verbose: false }), error: false };
  } catch {
    return { text: "Invalid cron expression", error: true };
  }
}

type ScrapeMode = "interval" | "times";

function ScheduleCard() {
  const qc = useQueryClient();

  const { data: schedule, isLoading } = useQuery<{ scrape_cron: string; scrape_times: string[]; next_scrape_at: string | null }>({
    queryKey: ["admin-schedule"],
    queryFn: () => api.get("/admin/schedule").then((r) => r.data),
    refetchInterval: 60_000,
  });

  const DEFAULT_CRON = "0 */6 * * *";
  const active_cron = schedule?.scrape_cron ?? "";
  const active_times = schedule?.scrape_times ?? [];

  const savedMode: ScrapeMode = active_times.length > 0 ? "times" : "interval";
  const [localMode, setLocalMode] = useState<ScrapeMode | null>(null);
  const mode: ScrapeMode = localMode ?? savedMode;

  const [draftCron, setDraftCron] = useState<string | null>(null);
  const editingCron = draftCron !== null ? draftCron : (active_cron || DEFAULT_CRON);
  const desc = cronDescription(editingCron);

  const save = useMutation({
    mutationFn: (body: { scrape_cron: string; scrape_times: string[] }) =>
      api.put("/admin/schedule", body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-schedule"] });
      setDraftCron(null);
      setLocalMode(null);
    },
  });

  function switchMode(next: ScrapeMode) {
    setLocalMode(next);
    if (next === "times") setDraftCron("");
  }

  function saveCron() {
    save.mutate({ scrape_cron: editingCron, scrape_times: [] });
  }

  function addTime(utcTime: string) {
    const next = [...new Set([...active_times, utcTime])].sort();
    save.mutate({ scrape_cron: "", scrape_times: next });
  }

  function removeTime(t: string) {
    save.mutate({ scrape_cron: "", scrape_times: active_times.filter((x) => x !== t) });
  }

  const isCronDirty = editingCron !== active_cron && !desc.error;

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">Scrape Schedule</h2>
          <p className="text-xs text-slate-500 mt-0.5">Global — scrapes all companies automatically.</p>
        </div>
        <div className="flex items-center bg-slate-800 border border-slate-700 rounded-lg p-0.5 shrink-0">
          {(["interval", "times"] as ScrapeMode[]).map((m) => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                mode === m ? "bg-slate-700 text-slate-100" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {m === "interval" ? "Interval" : "Specific times"}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <p className="text-xs text-slate-600">Loading…</p>
      ) : mode === "interval" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {SCRAPE_PRESETS.map((p) => (
              <button
                key={p.cron}
                onClick={() => setDraftCron(p.cron)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                  editingCron === p.cron
                    ? "bg-violet-600 border-violet-500 text-white"
                    : "bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Cron expression</label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={editingCron}
                onChange={(e) => setDraftCron(e.target.value)}
                placeholder="e.g. */30 * * * *"
                spellCheck={false}
                className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-violet-500 transition-colors"
              />
              <button
                onClick={saveCron}
                disabled={save.isPending || desc.error || !isCronDirty}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-xs font-semibold rounded-lg transition-colors shrink-0"
              >
                {save.isPending ? "Saving…" : "Save"}
              </button>
              {active_cron && (
                <button
                  onClick={() => { setDraftCron(""); save.mutate({ scrape_cron: "", scrape_times: [] }); }}
                  disabled={save.isPending}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 disabled:opacity-40 text-slate-400 text-xs font-medium rounded-lg transition-colors shrink-0"
                >
                  Clear
                </button>
              )}
            </div>
            <p className={`text-xs flex items-center gap-1.5 ${desc.error ? "text-red-400" : "text-slate-400"}`}>
              <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${desc.error ? "bg-red-400" : editingCron ? "bg-emerald-400" : "bg-slate-600"}`} />
              {desc.text}
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 min-h-[28px]">
            {active_times.length === 0 ? (
              <span className="text-xs text-slate-600 italic">No times set — runs manually only</span>
            ) : (
              active_times.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1.5 bg-slate-800 border border-slate-700/80 text-slate-200 text-xs font-medium rounded-lg px-3 py-1.5"
                >
                  {utcToIst(t)}
                  <button
                    onClick={() => removeTime(t)}
                    className="text-slate-500 hover:text-red-400 transition-colors leading-none"
                  >
                    ×
                  </button>
                </span>
              ))
            )}
          </div>
          <ISTTimePicker onAdd={addTime} disabled={save.isPending} />
        </div>
      )}
    </div>
  );
}

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
    <div className="mt-4 rounded-xl border border-slate-700/50 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-800/60 border-b border-slate-700/50">
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
      <div ref={scrollRef} className="max-h-72 overflow-y-auto bg-slate-900/60">
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
// Run card — inline expandable logs
// ---------------------------------------------------------------------------

const STATUS_PILL: Record<string, string> = {
  completed: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
  running:   "text-violet-400 bg-violet-400/10 border-violet-400/30",
  pending:   "text-violet-400 bg-violet-400/10 border-violet-400/30",
  failed:    "text-red-400 bg-red-400/10 border-red-400/30",
  cancelled: "text-amber-400 bg-amber-400/10 border-amber-400/30",
};

const STATUS_DOT: Record<string, string> = {
  completed: "bg-emerald-400",
  running:   "bg-violet-400 animate-pulse",
  pending:   "bg-violet-400 animate-pulse",
  failed:    "bg-red-400",
  cancelled: "bg-amber-400",
};

function RunCard({
  run,
  onResume,
  onStop,
}: {
  run: ScrapeRun;
  onResume: (id: number) => void;
  onStop: (id: number) => void;
}) {
  const active = run.status === "running" || run.status === "pending";
  const [showLogs, setShowLogs] = useState(active);
  useEffect(() => { if (active) setShowLogs(true); }, [active]);

  const pill = STATUS_PILL[run.status] ?? "text-slate-400 bg-slate-700/30 border-slate-600/30";
  const dot  = STATUS_DOT[run.status]  ?? "bg-slate-500";
  const pct  = run.companies_total > 0
    ? Math.round((run.companies_done / run.companies_total) * 100)
    : 0;

  return (
    <div className={`bg-slate-900 border rounded-xl overflow-hidden transition-colors ${active ? "border-violet-500/30" : "border-slate-800"}`}>
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          {/* Left */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border capitalize ${pill}`}>
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
              {run.status}
            </span>
            <div className="flex items-center gap-4 text-xs text-slate-500 tabular-nums flex-wrap">
              <span>Run #{run.id}</span>
              <span>{run.companies_done} / {run.companies_total} companies</span>
              {run.new_listings > 0 && (
                <span className="text-violet-400 font-medium">+{run.new_listings} new</span>
              )}
            </div>
          </div>

          {/* Right */}
          <div className="flex items-center gap-2 shrink-0">
            {run.started_at && (
              <span className="text-xs text-slate-600">
                {new Date(run.started_at).toLocaleString("en-IN", {
                  day: "numeric", month: "short",
                  hour: "2-digit", minute: "2-digit",
                })}
              </span>
            )}
            <button
              onClick={() => setShowLogs(v => !v)}
              className="text-xs text-slate-500 hover:text-slate-300 px-2.5 py-1 rounded-lg hover:bg-slate-800 border border-transparent hover:border-slate-700 transition-all"
            >
              {showLogs ? "Hide logs" : "Show logs"}
            </button>
            {(run.status === "failed" || run.status === "cancelled") && (
              <button
                onClick={() => onResume(run.id)}
                className="text-xs text-amber-400 hover:text-amber-300 font-medium px-2.5 py-1 rounded-lg hover:bg-amber-400/10 border border-amber-400/30 transition-colors"
              >
                Resume
              </button>
            )}
            {active && (
              <button
                onClick={() => { if (confirm("Stop the current scrape?")) onStop(run.id); }}
                className="text-xs text-red-400 hover:text-red-300 font-medium px-2.5 py-1 rounded-lg hover:bg-red-400/10 border border-red-400/30 transition-colors"
              >
                Stop
              </button>
            )}
          </div>
        </div>

        {active && run.companies_total > 0 && (
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-slate-600">Progress</span>
              <span className="text-[10px] text-slate-600 tabular-nums">{pct}%</span>
            </div>
            <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-violet-500 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}
      </div>

      {showLogs && (
        <div className="px-5 pb-5">
          <LogPanel runId={run.id} running={active} />
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

  const { data: companies = [] } = useQuery<Company[]>({
    queryKey: ["companies"],
    queryFn: () => api.get("/companies").then(r => r.data),
  });

  const { data: runs = [] } = useQuery<ScrapeRun[]>({
    queryKey: ["runs"],
    queryFn: () => api.get("/runs").then(r => r.data),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      return data.some(r => r.status === "running" || r.status === "pending") ? 2000 : false;
    },
  });

  const isRunning = runs.some(r => r.status === "running" || r.status === "pending");

  const startRun = useMutation({
    mutationFn: async () => {
      const company_ids = selected.size > 0 ? Array.from(selected) : null;
      return api.post("/scraper/run", { company_ids }).then(r => r.data);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });

  const resumeRun = useMutation({
    mutationFn: (runId: number) => api.post(`/scraper/resume/${runId}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
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
          Configure schedule and trigger scrape runs across your company list.
        </p>
      </div>

      {/* Schedule */}
      <ScheduleCard />

      {/* Manual trigger */}
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
              <span>Last run {new Date(runs[0].started_at!).toLocaleString()}</span>
            ) : (
              <span>No runs yet</span>
            )}
          </span>
          <button
            onClick={() => startRun.mutate()}
            disabled={isRunning || startRun.isPending}
            className="btn-primary"
          >
            {isRunning ? "Running…" : "Run Scrape"}
          </button>
        </div>
      </div>

      {/* Run history */}
      {runs.length > 0 && (
        <div className="space-y-4">
          {runs.map(run => (
            <RunCard
              key={run.id}
              run={run}
              onResume={id => resumeRun.mutate(id)}
              onStop={id => stopRun.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
