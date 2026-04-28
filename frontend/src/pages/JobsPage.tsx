import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api, { type Job } from "../api/client";
import { IconExternal } from "../components/Icons";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_OPTIONS = [
  "saved", "applied", "interviewing", "rejected",
  "offer", "withdrawn", "not_suitable",
] as const;

const STATUS_STYLES: Record<string, string> = {
  saved:        "bg-blue-500/15 text-blue-300 border-blue-500/30",
  applied:      "bg-violet-500/15 text-violet-300 border-violet-500/30",
  interviewing: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  rejected:     "bg-red-500/15 text-red-300 border-red-500/30",
  offer:        "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  withdrawn:    "bg-slate-500/10 text-slate-400 border-slate-600/30",
  not_suitable: "bg-slate-500/10 text-slate-400 border-slate-600/30",
};

const STATUS_DOT: Record<string, string> = {
  saved:        "bg-blue-400",
  applied:      "bg-violet-400",
  interviewing: "bg-amber-400",
  rejected:     "bg-red-400",
  offer:        "bg-emerald-400",
  withdrawn:    "bg-slate-500",
  not_suitable: "bg-slate-500",
};

const STATUS_LABEL: Record<string, string> = { not_suitable: "Not suitable" };

// ---------------------------------------------------------------------------
// Filter config
// ---------------------------------------------------------------------------

type FilterKey = "fresh" | "skipped" | "all";

interface FilterConfig {
  label: string;
  queryVerdict: string | null;
  clientFilter: ((job: Job) => boolean) | null;
}

const FRESH_STATUSES = new Set(["saved"]);

const FILTER_CONFIG: Record<FilterKey, FilterConfig> = {
  fresh:   { label: "Fresh",   queryVerdict: "apply", clientFilter: j => !j.application || FRESH_STATUSES.has(j.application.status) },
  skipped: { label: "Skipped", queryVerdict: "skip",  clientFilter: null },
  all:     { label: "All",     queryVerdict: null,    clientFilter: null },
};

const ALL_FILTERS: FilterKey[] = ["fresh", "skipped", "all"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreTier(score: number): "high" | "mid" | "low" {
  if (score >= 8) return "high";
  if (score >= 6) return "mid";
  return "low";
}

const TIER_BORDER: Record<string, string> = {
  high: "border-l-emerald-500",
  mid:  "border-l-amber-500",
  low:  "border-l-red-500/40",
};

const TIER_RING: Record<string, string> = {
  high: "border-emerald-500 text-emerald-400",
  mid:  "border-amber-500 text-amber-400",
  low:  "border-red-500/50 text-red-400",
};


function formatDateLabel(iso: string): string {
  const d = new Date(iso);
  d.setHours(0, 0, 0, 0);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  if (d.getTime() === today.getTime()) return "Today";
  if (d.getTime() === yesterday.getTime()) return "Yesterday";
  return d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
}

function groupByScrapedDate(jobs: Job[]): { dateKey: string; label: string; jobs: Job[] }[] {
  const map = new Map<string, Job[]>();
  for (const job of jobs) {
    const key = job.first_seen_at.split("T")[0];
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(job);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([dateKey, grpJobs]) => ({
      dateKey,
      label: formatDateLabel(dateKey + "T00:00:00"),
      // sort highest score first within each day
      jobs: [...grpJobs].sort((a, b) => (b.score?.score ?? -1) - (a.score?.score ?? -1)),
    }));
}

// ---------------------------------------------------------------------------
// Job card
// ---------------------------------------------------------------------------

function JobCard({ job }: { job: Job }) {
  const qc = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);

  const track = useMutation({
    mutationFn: (status: string) =>
      job.application
        ? api.patch(`/applications/${job.application!.id}`, { status }).then(r => r.data)
        : api.post("/applications", { listing_id: job.id, status }).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs"] }); setMenuOpen(false); },
  });

  const tier = job.score ? scoreTier(job.score.score) : null;
  const appStatus = job.application?.status;

  return (
    <div className={`card border-l-2 transition-colors hover:border-slate-700 ${tier ? TIER_BORDER[tier] : "border-l-slate-800"}`}>
      <div className="flex items-start gap-4 px-5 py-4">
        {/* Score */}
        <div className="shrink-0 flex items-center justify-center pt-0.5">
          {job.score ? (
            <div className={`w-12 h-12 rounded-full border-2 flex flex-col items-center justify-center ${TIER_RING[tier!]}`}>
              <span className="text-sm font-bold leading-none">{job.score.score.toFixed(1)}</span>
              <span className="text-[9px] text-slate-600 leading-none mt-0.5">/10</span>
            </div>
          ) : (
            <div className="w-12 h-12 rounded-full border-2 border-slate-700 flex items-center justify-center">
              <span className="text-xs text-slate-700">—</span>
            </div>
          )}
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <a
                href={job.url?.replace(/([^:])\/\/+/g, "$1/")}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 font-semibold text-slate-100 hover:text-violet-300 transition-colors group/link text-sm"
              >
                <span>{job.title}</span>
                <IconExternal className="w-3 h-3 opacity-0 group-hover/link:opacity-100 transition-opacity shrink-0" />
              </a>
              <p className="text-sm text-slate-400 mt-0.5">
                {job.company_name}
                {job.location && <span className="text-slate-600"> · {job.location}</span>}
              </p>
            </div>

            {/* Status + track dropdown */}
            <div className="flex items-center gap-2 shrink-0">
              {appStatus && (
                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border capitalize ${STATUS_STYLES[appStatus]}`}>
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[appStatus]}`} />
                  {STATUS_LABEL[appStatus] ?? appStatus}
                </span>
              )}
              <div className="relative">
                <button
                  onClick={() => setMenuOpen(o => !o)}
                  className="btn-ghost text-xs py-1 px-2.5 flex items-center gap-1"
                >
                  {appStatus ? "Update" : "Track"}
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {menuOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
                    <div className="absolute right-0 top-full mt-1 z-20 card p-1 flex flex-col min-w-[150px] shadow-xl">
                      {STATUS_OPTIONS.map(s => (
                        <button
                          key={s}
                          onClick={() => track.mutate(s)}
                          className={`text-left px-3 py-1.5 text-xs rounded-md capitalize transition-colors ${
                            appStatus === s
                              ? "bg-slate-700 text-slate-100"
                              : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                          }`}
                        >
                          {STATUS_LABEL[s] ?? s}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          {job.score?.reason && (
            <p className="mt-2 text-xs text-slate-500 leading-relaxed line-clamp-2">{job.score.reason}</p>
          )}

          <div className="mt-3 flex items-center gap-2.5 flex-wrap">
            {job.department && (
              <span className="badge bg-slate-800 text-slate-400 border border-slate-700/60">{job.department}</span>
            )}
            {job.posted_on && <span className="text-xs text-slate-600">{job.posted_on}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Date group
// ---------------------------------------------------------------------------

function DateGroup({ label, dateKey, jobs }: { label: string; dateKey: string; jobs: Job[] }) {
  const applyCount = jobs.filter(j => j.score?.verdict === "apply").length;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 px-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-300">{label}</span>
          <span className="text-xs text-slate-600">
            {new Date(dateKey + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
          </span>
        </div>
        <div className="flex-1 h-px bg-slate-800" />
        <span className="text-xs text-slate-600 shrink-0">
          {jobs.length} listing{jobs.length !== 1 ? "s" : ""}
          {applyCount > 0 && <span className="text-emerald-500 ml-1">· {applyCount} match</span>}
        </span>
      </div>
      <div className="space-y-2">
        {jobs.map(job => <JobCard key={job.id} job={job} />)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter tab group
// ---------------------------------------------------------------------------

function FilterGroup({
  keys, active, onSelect,
}: {
  keys: FilterKey[];
  active: FilterKey;
  onSelect: (k: FilterKey) => void;
}) {
  return (
    <div className="flex rounded-lg border border-slate-800 overflow-hidden">
      {keys.map(k => (
        <button
          key={k}
          onClick={() => onSelect(k)}
          className={`px-3.5 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
            active === k
              ? "bg-slate-800 text-slate-100"
              : "text-slate-500 hover:text-slate-300"
          }`}
        >
          {FILTER_CONFIG[k].label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function JobsPage() {
  const [filter, setFilter] = useState<FilterKey>("fresh");
  const [scoreMin, setScoreMin] = useState(7);

  const cfg = FILTER_CONFIG[filter];

  const { data: rawJobs = [], isLoading } = useQuery<Job[]>({
    queryKey: ["jobs", cfg.queryVerdict, filter === "fresh" ? scoreMin : null],
    queryFn: () =>
      api.get("/jobs", {
        params: {
          verdict: cfg.queryVerdict ?? undefined,
          score_min: filter === "fresh" ? scoreMin : undefined,
        },
      }).then(r => r.data),
  });

  const displayJobs = cfg.clientFilter ? rawJobs.filter(cfg.clientFilter) : rawJobs;
  const hiddenCount = filter === "fresh" ? rawJobs.length - displayJobs.length : 0;
  const groups = groupByScrapedDate(displayJobs);

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Jobs</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {displayJobs.length} listing{displayJobs.length !== 1 ? "s" : ""}
            {hiddenCount > 0 && (
              <span className="text-slate-700"> · {hiddenCount} reviewed hidden</span>
            )}
          </p>
        </div>
        <Link to="/scrape" className="btn-primary flex items-center gap-2 text-sm">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 18.364a9 9 0 010-12.728m12.728 0a9 9 0 010 12.728M8.464 15.536a5 5 0 010-7.072m7.072 0a5 5 0 010 7.072M12 12h.01" />
          </svg>
          Run Scrape
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterGroup keys={ALL_FILTERS} active={filter} onSelect={setFilter} />

        {filter === "fresh" && (
          <label className="flex items-center gap-2 text-xs text-slate-500 ml-1">
            Min score
            <input
              type="number" min={0.1} max={10} value={scoreMin}
              onChange={e => setScoreMin(Number(e.target.value))}
              step={0.1}
              className="w-16 bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-slate-100 text-center focus:outline-none focus:border-violet-500"
            />
          </label>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-6">
          {[0, 1].map(g => (
            <div key={g} className="space-y-2">
              <div className="h-5 w-32 bg-slate-800 rounded animate-pulse" />
              {[0, 1, 2].map(i => (
                <div key={i} className="card h-24 animate-pulse bg-slate-800/50" />
              ))}
            </div>
          ))}
        </div>
      ) : displayJobs.length === 0 ? (
        <div className="card p-16 text-center">
          <p className="text-slate-400 font-medium">
            {hiddenCount > 0 ? "All caught up!" : `No ${cfg.label.toLowerCase()} jobs`}
          </p>
          <p className="text-sm text-slate-600 mt-1">
            {hiddenCount > 0
              ? `${hiddenCount} job${hiddenCount !== 1 ? "s" : ""} already reviewed — switch to "All" to see them.`
              : filter === "fresh"
                ? <><Link to="/scrape" className="text-violet-400 hover:text-violet-300 transition-colors">Run a scrape</Link> to populate listings.</>
                : "Nothing here yet."
            }
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {groups.map(g => (
            <DateGroup key={g.dateKey} label={g.label} dateKey={g.dateKey} jobs={g.jobs} />
          ))}
        </div>
      )}
    </div>
  );
}
