import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { type ScrapeStatus } from "../api/client";

export default function RunButton() {
  const qc = useQueryClient();

  const { data: status } = useQuery<ScrapeStatus>({
    queryKey: ["scraper-status"],
    queryFn: () => api.get("/scraper/status").then((r) => r.data),
    refetchInterval: (query) => (query.state.data?.running ? 3000 : false),
  });

  const run = useMutation({
    mutationFn: () => api.post("/scraper/run", { company_ids: null }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scraper-status"] }),
  });

  const running = status?.running ?? false;

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => run.mutate()}
        disabled={running}
        className="px-4 py-2 text-sm font-medium rounded-md bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {running ? "Scraping…" : "Run Scrape"}
      </button>
      {status?.result && !running && (
        <span className="text-xs text-gray-400">
          Last run: {status.result.apply_count} matches / {status.result.new_listings} new
        </span>
      )}
    </div>
  );
}
