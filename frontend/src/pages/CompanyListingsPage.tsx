import { useState, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { type Company, type JobListing, type AppRecord } from "../api/client";
import { IconExternal } from "../components/Icons";

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
// Track button — uses a portal so the menu is never clipped by overflow:hidden
// ---------------------------------------------------------------------------

function TrackButton({ listing, app }: { listing: JobListing; app: AppRecord | undefined }) {
  const qc = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState<{ top: number; right: number }>({ top: 0, right: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);

  const track = useMutation({
    mutationFn: (status: string) =>
      app
        ? api.patch(`/applications/${app.id}`, { status }).then((r) => r.data)
        : api.post("/applications", { listing_id: listing.id, status }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scan-applications"] });
      setMenuOpen(false);
    },
  });

  function openMenu() {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    // ~7 items × 30px + 8px padding ≈ 220px menu height
    const spaceBelow = window.innerHeight - rect.bottom;
    const top = spaceBelow < 228 ? rect.top - 228 - 4 : rect.bottom + 4;
    setMenuStyle({ top, right: window.innerWidth - rect.right });
    setMenuOpen((o) => !o);
  }

  const appStatus = app?.status;

  return (
    <div>
      <button
        ref={btnRef}
        onClick={openMenu}
        className="btn-ghost text-xs py-1 px-2.5 flex items-center gap-1"
      >
        {appStatus ? "Update" : "Track"}
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {menuOpen && createPortal(
        <>
          <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
          <div
            className="fixed z-50 card p-1 flex flex-col min-w-[150px] shadow-xl"
            style={{ top: menuStyle.top, right: menuStyle.right }}
          >
            {STATUS_OPTIONS.map((s) => (
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
        </>,
        document.body
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function CompanyListingsPage() {
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  const { data: companies = [] } = useQuery<Company[]>({
    queryKey: ["companies"],
    queryFn: () => api.get("/companies").then((r) => r.data),
  });

  const company = companies.find((c) => c.id === Number(companyId));

  const { data, isLoading } = useQuery<{ total: number; items: JobListing[] }>({
    queryKey: ["listings", companyId],
    queryFn: () =>
      api
        .get("/listings", { params: { company_id: companyId, days_back: 0, limit: 500 } })
        .then((r) => r.data),
    enabled: !!companyId,
  });

  const { data: applications = [] } = useQuery<AppRecord[]>({
    queryKey: ["scan-applications"],
    queryFn: () => api.get("/applications").then((r) => r.data),
  });

  const appByListingId = useMemo(() => {
    const map = new Map<number, AppRecord>();
    for (const a of applications) map.set(a.listing_id, a);
    return map;
  }, [applications]);

  const filtered = useMemo(() => {
    if (!data?.items) return [];
    // Sort newest first by job posting date; nulls go to the end
    const sorted = [...data.items].sort((a, b) => {
      if (!a.posted_date && !b.posted_date) return 0;
      if (!a.posted_date) return 1;
      if (!b.posted_date) return -1;
      return new Date(b.posted_date).getTime() - new Date(a.posted_date).getTime();
    });
    const q = search.toLowerCase().trim();
    if (!q) return sorted;
    return sorted.filter(
      (l) =>
        l.title.toLowerCase().includes(q) ||
        (l.location ?? "").toLowerCase().includes(q) ||
        (l.department ?? "").toLowerCase().includes(q)
    );
  }, [data?.items, search]);

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => navigate("/scan")}
          className="mt-1 text-slate-500 hover:text-slate-300 transition-colors shrink-0"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div>
          <h1 className="text-xl font-semibold text-slate-100">
            {company?.name ?? "Openings"}
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {isLoading
              ? "Loading…"
              : data
              ? `${data.total} listing${data.total !== 1 ? "s" : ""}`
              : ""}
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <svg
          className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"
          />
        </svg>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by title, location, or department…"
          className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-10 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-colors"
        />
        {search && (
          <button
            onClick={() => setSearch("")}
            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {search && !isLoading && (
        <p className="text-xs text-slate-500 -mt-3">
          {filtered.length} result{filtered.length !== 1 ? "s" : ""} for &ldquo;{search}&rdquo;
        </p>
      )}

      {/* Listings */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="px-5 py-16 text-center text-slate-600 text-sm">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="px-5 py-16 text-center text-slate-600 text-sm">
            {search ? `No results for "${search}".` : "No listings found."}
          </div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {filtered.map((l) => {
              const app = appByListingId.get(l.id);
              const appStatus = app?.status;
              return (
                <div
                  key={l.id}
                  className="px-5 py-3.5 flex items-center justify-between gap-4 hover:bg-slate-800/30 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-200 font-medium leading-snug">{l.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {l.location || "—"}
                      {l.department ? ` · ${l.department}` : ""}
                      {l.posted_on ? ` · ${l.posted_on}` : ""}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {appStatus && (
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border capitalize ${STATUS_STYLES[appStatus]}`}>
                        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[appStatus]}`} />
                        {STATUS_LABEL[appStatus] ?? appStatus}
                      </span>
                    )}

                    <TrackButton listing={l} app={app} />

                    {l.url && (
                      <a
                        href={l.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300 transition-colors border border-violet-500/20 hover:border-violet-500/40 rounded-lg px-2.5 py-1.5"
                      >
                        Apply
                        <IconExternal className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
