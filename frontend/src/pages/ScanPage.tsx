import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api, { type Company } from "../api/client";

function CompanyCard({
  company,
  onClick,
}: {
  company: Company;
  onClick: () => void;
}) {
  const hasListings = company.listing_count > 0;

  return (
    <button
      onClick={onClick}
      className={`text-left rounded-xl border p-4 transition-all duration-200 w-full ${
        hasListings
          ? "bg-slate-900 border-slate-800 hover:border-violet-500/40 hover:bg-slate-800/60"
          : "bg-slate-900/50 border-slate-800/50 opacity-40 cursor-default pointer-events-none"
      }`}
    >
      <p className="text-sm font-medium text-slate-200 leading-tight line-clamp-2 mb-2">
        {company.name}
      </p>
      <span
        className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
          hasListings
            ? "text-slate-400 bg-slate-800"
            : "text-slate-600 bg-slate-800/50"
        }`}
      >
        {company.listing_count} listing{company.listing_count !== 1 ? "s" : ""}
      </span>
    </button>
  );
}

export default function ScanPage() {
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const { data: companies = [] } = useQuery<Company[]>({
    queryKey: ["companies"],
    queryFn: () => api.get("/companies").then((r) => r.data),
  });

  const withListings = companies.filter((c) => c.listing_count > 0);
  const withoutListings = companies.filter((c) => c.listing_count === 0);
  const sorted = [...withListings, ...withoutListings];

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return sorted;
    return sorted.filter((c) => c.name.toLowerCase().includes(q));
  }, [sorted, search]);

  return (
    <div className="w-full space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Find Openings</h1>
        <p className="text-sm text-slate-500 mt-0.5">Browse job listings by company</p>
      </div>

      {/* Search companies */}
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
          placeholder="Search companies…"
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

      {companies.length === 0 ? (
        <div className="text-center py-20 text-slate-600 text-sm">No companies configured yet.</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-slate-600 text-sm">
          No companies match &ldquo;{search}&rdquo;.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
          {filtered.map((company) => (
            <CompanyCard
              key={company.id}
              company={company}
              onClick={() => {
                if (company.listing_count > 0) navigate(`/scan/${company.id}`);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
