import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { type AdminScoreRun } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { IconScan } from "../components/Icons";

interface UserRow {
  id: number;
  email: string;
  name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
}

const STATUS_DOT: Record<string, string> = {
  completed: "bg-emerald-400",
  running:   "bg-violet-400 animate-pulse",
  pending:   "bg-violet-400 animate-pulse",
  failed:    "bg-red-400",
  cancelled: "bg-amber-400",
};

// ---------------------------------------------------------------------------
// Toggle
// ---------------------------------------------------------------------------

function Toggle({
  enabled, disabled, color, onChange,
}: {
  enabled: boolean; disabled: boolean; color: "violet" | "emerald"; onChange: (v: boolean) => void;
}) {
  const track = color === "violet"
    ? enabled ? "bg-violet-600" : "bg-slate-700"
    : enabled ? "bg-emerald-600" : "bg-slate-700";

  return (
    <button
      disabled={disabled}
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-5 w-9 rounded-full transition-colors duration-200 focus:outline-none ${track} ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${enabled ? "translate-x-4" : "translate-x-0"}`} />
    </button>
  );
}

// ---------------------------------------------------------------------------
// User row
// ---------------------------------------------------------------------------

function UserTableRow({
  user,
  isSelf,
  latestRun,
  runCount,
  onPatch,
  onScore,
  onDelete,
  onClick,
}: {
  user: UserRow;
  isSelf: boolean;
  latestRun: AdminScoreRun | undefined;
  runCount: number;
  onPatch: (body: Record<string, unknown>) => void;
  onScore: () => void;
  onDelete: () => void;
  onClick: () => void;
}) {
  const dot = latestRun ? (STATUS_DOT[latestRun.status] ?? "bg-slate-500") : null;

  return (
    <tr
      className="hover:bg-slate-800/30 transition-colors cursor-pointer group"
      onClick={onClick}
    >
      {/* User */}
      <td className="px-5 py-3.5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-semibold text-slate-300 shrink-0">
            {(user.name || user.email)[0].toUpperCase()}
          </div>
          <div>
            <p className="text-slate-200 font-medium leading-tight">
              {user.name || <span className="text-slate-500 italic">No name</span>}
              {isSelf && (
                <span className="ml-2 text-[10px] text-violet-400 bg-violet-500/10 px-1.5 py-0.5 rounded-full">you</span>
              )}
            </p>
            <p className="text-xs text-slate-500">{user.email}</p>
          </div>
        </div>
      </td>

      {/* Joined */}
      <td className="px-5 py-3.5 text-xs text-slate-500">
        {new Date(user.created_at).toLocaleDateString("en-IN", {
          day: "numeric", month: "short", year: "numeric",
        })}
      </td>

      {/* Scoring summary */}
      <td className="px-4 py-3.5">
        {runCount > 0 ? (
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
            <span className="text-xs text-slate-400">{latestRun!.status}</span>
            <span className="text-xs text-slate-600">· {runCount} run{runCount !== 1 ? "s" : ""}</span>
          </div>
        ) : (
          <span className="text-xs text-slate-700">—</span>
        )}
      </td>

      {/* Admin toggle */}
      <td className="px-4 py-3.5 text-center" onClick={(e) => e.stopPropagation()}>
        <Toggle enabled={user.is_admin} disabled={isSelf} color="violet" onChange={(v) => onPatch({ is_admin: v })} />
      </td>

      {/* Active toggle */}
      <td className="px-4 py-3.5 text-center" onClick={(e) => e.stopPropagation()}>
        <Toggle enabled={user.is_active} disabled={isSelf} color="emerald" onChange={(v) => onPatch({ is_active: v })} />
      </td>

      {/* Actions */}
      <td className="px-4 py-3.5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-end gap-1">
          <button
            onClick={onScore}
            title="Run scoring for this user"
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-violet-400 transition-colors px-2 py-1 rounded hover:bg-violet-400/5"
          >
            <IconScan className="w-3.5 h-3.5" />
            Score
          </button>
          {!isSelf && (
            <button
              onClick={onDelete}
              className="text-xs text-slate-600 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-red-400/5"
            >
              Delete
            </button>
          )}
          <svg
            className="w-3.5 h-3.5 text-slate-700 group-hover:text-slate-500 transition-colors ml-1"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AdminPage() {
  const { user: me } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [daysBack, setDaysBack] = useState("1");
  const [lastResult, setLastResult] = useState<{ started: number; skipped: number } | null>(null);

  const { data: users = [], isLoading } = useQuery<UserRow[]>({
    queryKey: ["admin-users"],
    queryFn: () => api.get("/admin/users").then((r) => r.data),
  });

  const { data: allRuns = [] } = useQuery<AdminScoreRun[]>({
    queryKey: ["admin-score-runs"],
    queryFn: () => api.get("/admin/score/runs").then((r) => r.data),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      return data.some((r) => r.status === "pending" || r.status === "running") ? 2000 : false;
    },
  });

  // Latest run + count per user
  const runsByUser = allRuns.reduce((acc, r) => {
    if (!acc.has(r.user_id)) acc.set(r.user_id, []);
    acc.get(r.user_id)!.push(r);
    return acc;
  }, new Map<number, AdminScoreRun[]>());

  const hasActive = allRuns.some((r) => r.status === "pending" || r.status === "running");

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api.patch(`/admin/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/admin/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const scoreUser = useMutation({
    mutationFn: (id: number) =>
      api.post(`/admin/score/run/${id}`, { days_back: daysBack ? parseInt(daysBack) : null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-score-runs"] }),
  });

  const runAll = useMutation({
    mutationFn: () =>
      api.post("/admin/score/run-all", { days_back: daysBack ? parseInt(daysBack) : null }).then((r) => r.data),
    onSuccess: (data) => {
      setLastResult({ started: data.started.length, skipped: data.skipped.length });
      qc.invalidateQueries({ queryKey: ["admin-score-runs"] });
    },
  });

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Admin</h1>
          <p className="text-sm text-slate-500 mt-0.5">Click a user to view their scoring history</p>
        </div>
        <div className="flex items-center gap-3">
          {lastResult && (
            <span className="text-xs text-slate-500">
              {lastResult.started} started · {lastResult.skipped} skipped
            </span>
          )}
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
            onClick={() => runAll.mutate()}
            disabled={runAll.isPending || hasActive}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition"
          >
            {runAll.isPending ? "Starting…" : hasActive ? "Running…" : "Run for All Users"}
          </button>
        </div>
      </div>

      {/* Users */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-xs text-slate-500 uppercase tracking-wider">
              <th className="text-left px-5 py-3 font-medium">User</th>
              <th className="text-left px-5 py-3 font-medium">Joined</th>
              <th className="text-left px-4 py-3 font-medium">Last scoring</th>
              <th className="text-center px-4 py-3 font-medium">Admin</th>
              <th className="text-center px-4 py-3 font-medium">Active</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-slate-600 text-sm">Loading…</td>
              </tr>
            ) : (
              users.map((u) => {
                const userRuns = runsByUser.get(u.id) ?? [];
                return (
                  <UserTableRow
                    key={u.id}
                    user={u}
                    isSelf={u.id === me?.user_id}
                    latestRun={userRuns[0]}
                    runCount={userRuns.length}
                    onPatch={(body) => patch.mutate({ id: u.id, body })}
                    onScore={() => scoreUser.mutate(u.id)}
                    onDelete={() => {
                      if (confirm(`Delete ${u.email}? This cannot be undone.`)) {
                        remove.mutate(u.id);
                      }
                    }}
                    onClick={() => navigate(`/admin/scoring/${u.id}`)}
                  />
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
