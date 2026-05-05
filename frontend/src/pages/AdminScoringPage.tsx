import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { type Company, type AdminScoreRun } from "../api/client";
import { IconChevronDown } from "../components/Icons";
import { ISTTimePicker, utcToIst } from "../components/ISTTimePicker";

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
// Constants
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

const LOG_LEVEL: Record<string, { badge: string; text: string }> = {
  error:   { badge: "text-red-400 bg-red-400/10 border-red-400/20",             text: "text-red-300" },
  warning: { badge: "text-amber-400 bg-amber-400/10 border-amber-400/20",       text: "text-amber-200" },
  success: { badge: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20", text: "text-slate-200" },
  info:    { badge: "text-slate-400 bg-slate-700/40 border-slate-600/30",        text: "text-slate-400" },
};

// ---------------------------------------------------------------------------
// Logs panel — streams live when active
// ---------------------------------------------------------------------------

interface LogEntry { id: number; timestamp: string; level: string; message: string; }

function LogsPanel({ runId, active }: { runId: number; active: boolean }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastIdRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await api.get(`/admin/score/runs/${runId}/logs`, {
          params: { after_id: lastIdRef.current },
        });
        if (cancelled || !res.data.length) return;
        lastIdRef.current = res.data[res.data.length - 1].id;
        setLogs((prev) => [...prev, ...res.data]);
      } catch {}
    };
    poll();
    if (!active) return;
    const t = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(t); };
  }, [runId, active]);

  // Scroll the container itself — never the page
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  return (
    <div className="mt-4 rounded-xl border border-slate-700/50 overflow-hidden">
      {/* Log header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-800/60 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          {active && (
            <span className="flex items-center gap-1.5 text-xs text-violet-400">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
              Live
            </span>
          )}
          {!active && <span className="text-xs text-slate-500">Logs</span>}
        </div>
        <span className="text-xs text-slate-600">{logs.length} entr{logs.length === 1 ? "y" : "ies"}</span>
      </div>

      {/* Log entries */}
      <div ref={scrollRef} className="max-h-72 overflow-y-auto bg-slate-900/60">
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 gap-2">
            {active
              ? <span className="text-xs text-slate-600 animate-pulse">Waiting for logs…</span>
              : <span className="text-xs text-slate-700">No logs recorded</span>}
          </div>
        ) : (
          <div className="divide-y divide-slate-800/50">
            {logs.map((l) => {
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
                  <span className={`text-xs leading-snug break-words flex-1 min-w-0 ${style.text}`}>
                    {l.message}
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
// Single run card
// ---------------------------------------------------------------------------

function RunCard({ r, onStop }: { r: AdminScoreRun; onStop: () => void }) {
  const active = r.status === "pending" || r.status === "running";
  const [showLogs, setShowLogs] = useState(active);
  useEffect(() => { if (active) setShowLogs(true); }, [active]);

  const pill = STATUS_PILL[r.status] ?? "text-slate-400 bg-slate-700/30 border-slate-600/30";
  const dot  = STATUS_DOT[r.status]  ?? "bg-slate-500";

  const pct = r.companies_total > 0
    ? Math.round((r.companies_done / r.companies_total) * 100)
    : 0;

  return (
    <div className={`bg-slate-900 border rounded-xl overflow-hidden transition-colors ${active ? "border-violet-500/30" : "border-slate-800"}`}>
      {/* Run summary bar */}
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          {/* Left */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border capitalize ${pill}`}>
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
              {r.status}
            </span>
            <div className="flex items-center gap-4 text-xs text-slate-500 tabular-nums flex-wrap">
              <span>{r.companies_done} / {r.companies_total} companies</span>
              {r.days_back != null && <span className="text-slate-600">{r.days_back}d back</span>}
              <span className="text-emerald-400 font-medium">{r.apply_count} match{r.apply_count !== 1 ? "es" : ""}</span>
              {r.input_tokens > 0 && (
                <span className="text-slate-600">
                  {(r.input_tokens / 1000).toFixed(1)}k / {(r.output_tokens / 1000).toFixed(1)}k tok
                </span>
              )}
              {r.cost_usd > 0 && (
                <span className="text-amber-400/80 font-medium">
                  ₹{(r.cost_usd * 84).toFixed(2)}
                </span>
              )}
            </div>
          </div>

          {/* Right */}
          <div className="flex items-center gap-2 shrink-0">
            {r.started_at && (
              <span className="text-xs text-slate-600">
                {new Date(r.started_at).toLocaleString("en-IN", {
                  day: "numeric", month: "short",
                  hour: "2-digit", minute: "2-digit",
                })}
              </span>
            )}
            <button
              onClick={() => setShowLogs((v) => !v)}
              className="text-xs text-slate-500 hover:text-slate-300 px-2.5 py-1 rounded-lg hover:bg-slate-800 border border-transparent hover:border-slate-700 transition-all"
            >
              {showLogs ? "Hide logs" : "Show logs"}
            </button>
            {active && (
              <button
                onClick={onStop}
                className="text-xs text-red-400 hover:text-red-300 font-medium px-2.5 py-1 rounded-lg hover:bg-red-400/10 border border-red-400/30 transition-colors"
              >
                Stop
              </button>
            )}
          </div>
        </div>

        {/* Progress bar for active runs */}
        {active && r.companies_total > 0 && (
          <div className="mt-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-slate-600">Progress</span>
              <span className="text-[10px] text-slate-600 tabular-nums">{pct}%</span>
            </div>
            <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-violet-500 rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {showLogs && (
        <div className="px-5 pb-5">
          <LogsPanel runId={r.id} active={active} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-user score schedule
// ---------------------------------------------------------------------------

function UserScoreSchedule({ userId }: { userId: string }) {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<{ score_times: string[] }>({
    queryKey: ["user-score-schedule", userId],
    queryFn: () => api.get(`/admin/users/${userId}/score-schedule`).then((r) => r.data),
  });

  const save = useMutation({
    mutationFn: (score_times: string[]) =>
      api.put(`/admin/users/${userId}/score-schedule`, { score_times }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user-score-schedule", userId] }),
  });

  const times = data?.score_times ?? [];

  function addTime(utcTime: string) {
    const next = [...new Set([...times, utcTime])].sort();
    save.mutate(next);
  }

  function removeTime(t: string) {
    save.mutate(times.filter((x) => x !== t));
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl px-5 py-4 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">Score Schedule</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Scoring runs automatically for this user at these times.
          </p>
        </div>
        {save.isPending && <span className="text-xs text-slate-500 shrink-0">Saving…</span>}
      </div>

      {isLoading ? (
        <p className="text-xs text-slate-600">Loading…</p>
      ) : (
        <div className="space-y-3">
          {/* Time chips */}
          <div className="flex flex-wrap gap-2 min-h-[28px]">
            {times.length === 0 ? (
              <span className="text-xs text-slate-600 italic">No times set — runs manually only</span>
            ) : (
              times.map((t) => (
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

          {/* Picker */}
          <ISTTimePicker onAdd={addTime} disabled={save.isPending} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

interface UserInfo { id: number; email: string; name: string; }

export default function AdminScoringPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [daysBack, setDaysBack] = useState("1");
  const [selectedCompanies, setSelectedCompanies] = useState<Set<number>>(new Set());

  const { data: companies = [] } = useQuery<Company[]>({
    queryKey: ["companies"],
    queryFn: () => api.get("/companies").then(r => r.data),
  });
  const activeCompanies = companies.filter(c => c.active);

  // Fetch all users to get name/email for the header
  const { data: users = [] } = useQuery<UserInfo[]>({
    queryKey: ["admin-users"],
    queryFn: () => api.get("/admin/users").then((r) => r.data),
  });
  const user = users.find((u) => u.id === Number(userId));

  const { data: runs = [], isLoading } = useQuery<AdminScoreRun[]>({
    queryKey: ["admin-score-runs"],
    queryFn: () => api.get("/admin/score/runs").then((r) => r.data),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      return data.some((r) => r.status === "pending" || r.status === "running") ? 2000 : false;
    },
  });

  // Filter to this user only
  const userRuns = runs.filter((r) => r.user_id === Number(userId));

  const score = useMutation({
    mutationFn: () =>
      api.post(`/admin/score/run/${userId}`, {
        days_back: daysBack ? parseInt(daysBack) : null,
        company_ids: selectedCompanies.size > 0 ? Array.from(selectedCompanies) : null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-score-runs"] }),
  });

  const stopRun = useMutation({
    mutationFn: (id: number) => api.post(`/admin/score/runs/${id}/stop`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-score-runs"] }),
  });

  const hasActive = userRuns.some((r) => r.status === "pending" || r.status === "running");

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => navigate("/admin")}
          className="mt-1 text-slate-500 hover:text-slate-300 transition-colors shrink-0"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">
              {user?.name || user?.email || `User #${userId}`}
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">
              {user?.email && user.name ? user.email : "Scoring history"}
              {userRuns.length > 0 && ` · ${userRuns.length} run${userRuns.length !== 1 ? "s" : ""}`}
            </p>
          </div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <div className="w-48">
              <CompanySelector
                companies={activeCompanies}
                selected={selectedCompanies}
                onChange={setSelectedCompanies}
              />
            </div>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={1}
                value={daysBack}
                onChange={(e) => setDaysBack(e.target.value)}
                className="w-16 text-sm bg-slate-900 border border-slate-700 text-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500/60 text-center"
              />
              <span className="text-xs text-slate-500">days</span>
            </div>
            <button
              onClick={() => score.mutate()}
              disabled={score.isPending || hasActive}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition"
            >
              {score.isPending ? "Starting…" : hasActive ? "Running…" : "Run Scoring"}
            </button>
          </div>
        </div>
      </div>

      {/* Score schedule */}
      {userId && <UserScoreSchedule userId={userId} />}

      {/* Runs */}
      {isLoading ? (
        <div className="py-20 text-center text-slate-600 text-sm">Loading…</div>
      ) : userRuns.length === 0 ? (
        <div className="py-20 text-center text-slate-600 text-sm">No scoring runs yet for this user.</div>
      ) : (
        <div className="space-y-4">
          {userRuns.map((r) => (
            <RunCard key={r.id} r={r} onStop={() => stopRun.mutate(r.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
