import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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

type TabKey = "all" | typeof STATUS_OPTIONS[number];

const TABS: { key: TabKey; label: string }[] = [
  { key: "all",          label: "All" },
  { key: "applied",      label: "Applied" },
  { key: "interviewing", label: "Interviewing" },
  { key: "offer",        label: "Offer" },
  { key: "saved",        label: "Saved" },
  { key: "rejected",     label: "Rejected" },
  { key: "withdrawn",    label: "Withdrawn" },
  { key: "not_suitable", label: "Not suitable" },
];

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
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs", "applied"] }); setMenuOpen(false); },
  });

  const tier = job.score ? scoreTier(job.score.score) : null;
  const appStatus = job.application?.status;

  return (
    <div className={`card border-l-2 transition-colors hover:border-slate-700 ${tier ? TIER_BORDER[tier] : "border-l-slate-800"}`}>
      <div className="flex items-start gap-3 px-3 py-3 sm:gap-4 sm:px-5 sm:py-4">
        {/* Score */}
        <div className="shrink-0 flex items-center justify-center pt-0.5">
          {job.score ? (
            <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-full border-2 flex flex-col items-center justify-center ${TIER_RING[tier!]}`}>
              <span className="text-xs sm:text-sm font-bold leading-none">{job.score.score.toFixed(1)}</span>
              <span className="text-[8px] sm:text-[9px] text-slate-600 leading-none mt-0.5">/10</span>
            </div>
          ) : (
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full border-2 border-slate-700 flex items-center justify-center">
              <span className="text-xs text-slate-700">—</span>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 sm:gap-4">
            <div className="min-w-0 flex-1">
              <a
                href={job.url?.replace(/([^:])\/\/+/g, "$1/")}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-1.5 font-semibold text-slate-100 hover:text-violet-300 transition-colors group/link text-sm"
              >
                <span className="line-clamp-2 sm:line-clamp-1">{job.title}</span>
                <IconExternal className="w-3 h-3 opacity-0 group-hover/link:opacity-100 transition-opacity shrink-0 mt-0.5" />
              </a>
              <p className="text-sm text-slate-400 mt-0.5 line-clamp-2 sm:line-clamp-1">
                {job.company_name}
                {job.location && <span className="text-slate-600"> · {job.location}</span>}
              </p>
            </div>

            {/* Status badge + dropdown */}
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              {appStatus && (
                <span className={`inline-flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1 rounded-full text-xs font-medium border capitalize ${STATUS_STYLES[appStatus]}`}>
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[appStatus]}`} />
                  <span className="hidden sm:inline">{STATUS_LABEL[appStatus] ?? appStatus}</span>
                </span>
              )}
              <div className="relative">
                <button
                  onClick={() => setMenuOpen(o => !o)}
                  className="btn-ghost text-xs py-1 px-2.5 flex items-center gap-1"
                >
                  {appStatus ? "update" : "track"}
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
              <span className="badge bg-slate-800 text-slate-400 border border-slate-700/60" title={job.department}>{job.department}</span>
            )}
            {job.posted_on && <span className="text-xs text-slate-600">{job.posted_on}</span>}
            {job.application?.applied_at && (
              <span className="text-xs text-slate-600">
                Applied {new Date(job.application.applied_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ApplicationsPage() {
  const [tab, setTab] = useState<TabKey>("applied");

  const { data: tracked = [], isLoading } = useQuery<Job[]>({
    queryKey: ["jobs", "applied"],
    queryFn: () => api.get("/jobs?has_application=true").then(r => r.data),
  });
  const displayed = tab === "all"
    ? tracked
    : tracked.filter(j => j.application?.status === tab);

  // Count per tab
  const counts: Record<string, number> = { all: tracked.length };
  for (const j of tracked) {
    const s = j.application!.status;
    counts[s] = (counts[s] ?? 0) + 1;
  }

  // Sort by score desc
  const sorted = [...displayed].sort((a, b) => (b.score?.score ?? -1) - (a.score?.score ?? -1));

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Applications</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {tracked.length} tracked · {counts["applied"] ?? 0} applied · {counts["interviewing"] ?? 0} interviewing
        </p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1.5">
        {TABS.map(t => {
          const count = counts[t.key] ?? 0;
          if (t.key !== "all" && count === 0) return null;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                tab === t.key
                  ? "bg-slate-800 text-slate-100"
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/50"
              }`}
            >
              {t.label}
              {count > 0 && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                  tab === t.key ? "bg-slate-700 text-slate-300" : "bg-slate-800/80 text-slate-500"
                }`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2].map(i => <div key={i} className="card h-24 animate-pulse bg-slate-800/50" />)}
        </div>
      ) : sorted.length === 0 ? (
        <div className="card p-16 text-center">
          <p className="text-slate-400 font-medium">
            {tracked.length === 0 ? "No applications tracked yet" : `No ${tab === "all" ? "" : tab + " "}jobs`}
          </p>
          <p className="text-sm text-slate-600 mt-1">
            {tracked.length === 0
              ? "Use the track button on any job in the Jobs page to get started."
              : "Switch tabs to see other statuses."}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {sorted.map(job => <JobCard key={job.id} job={job} />)}
        </div>
      )}
    </div>
  );
}
