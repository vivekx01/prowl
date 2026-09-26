import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { type AdminScoreRun, type ModelConfig } from "../api/client";
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
      <td className="px-5 py-3.5 text-xs text-slate-500 hidden sm:table-cell">
        {new Date(user.created_at).toLocaleDateString("en-IN", {
          day: "numeric", month: "short", year: "numeric",
        })}
      </td>

      {/* Scoring summary */}
      <td className="px-4 py-3.5 hidden md:table-cell">
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

function CreateUserModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ email: "", password: "", name: "", is_admin: false });
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () => api.post("/admin/users", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      onClose();
    },
    onError: (err: any) => setError(err.response?.data?.detail ?? "Something went wrong"),
  });

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-sm space-y-4">
        <h2 className="text-base font-semibold text-slate-100">Create User</h2>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5">Name</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Full name"
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 transition"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5">Email</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            placeholder="user@example.com"
            required
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 transition"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5">Password</label>
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            placeholder="••••••••"
            required
            minLength={6}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 transition"
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_admin}
            onChange={(e) => setForm((f) => ({ ...f, is_admin: e.target.checked }))}
            className="rounded border-slate-600 bg-slate-800 text-violet-600 focus:ring-violet-500"
          />
          Admin access
        </label>

        {error && (
          <p className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">{error}</p>
        )}

        <div className="flex gap-2 pt-1">
          <button
            onClick={() => create.mutate()}
            disabled={create.isPending || !form.email || !form.password}
            className="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg py-2 transition"
          >
            {create.isPending ? "Creating…" : "Create"}
          </button>
          <button
            onClick={onClose}
            className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg py-2 transition"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Model configuration
// ---------------------------------------------------------------------------

function ModelConfigSection() {
  const qc = useQueryClient();
  const [form, setForm] = useState<ModelConfig | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useQuery<ModelConfig>({
    queryKey: ["model-config"],
    queryFn: () => api.get("/admin/model-config").then((r) => r.data),
  });

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const save = useMutation({
    mutationFn: (body: ModelConfig) =>
      api.put("/admin/model-config", body).then((r) => r.data),
    onSuccess: (updated: ModelConfig) => {
      qc.setQueryData(["model-config"], updated);
      setForm(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  function setField<K extends keyof ModelConfig>(key: K, val: ModelConfig[K]) {
    setForm((f) => f ? { ...f, [key]: val } : f);
  }

  function numInput(key: keyof ModelConfig, label: string, opts?: { step?: string; min?: number; max?: number }) {
    const val = form ? (form[key] as number) : 0;
    return (
      <div>
        <label className="block text-xs text-slate-500 mb-1">{label}</label>
        <input
          type="number"
          value={val}
          step={opts?.step ?? "0.0001"}
          min={opts?.min ?? 0}
          max={opts?.max}
          onChange={(e) => setField(key, parseFloat(e.target.value) || 0 as any)}
          className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500/60 tabular-nums"
        />
      </div>
    );
  }

  function textInput(key: keyof ModelConfig, label: string, placeholder?: string) {
    const val = form ? (form[key] as string) : "";
    return (
      <div>
        <label className="block text-xs text-slate-500 mb-1">{label}</label>
        <input
          type="text"
          value={val}
          placeholder={placeholder}
          onChange={(e) => setField(key, e.target.value as any)}
          className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500/60 font-mono"
        />
      </div>
    );
  }

  const isDirty = form && data && JSON.stringify(form) !== JSON.stringify(data);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">Model Configuration</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            OpenRouter model IDs and pricing used for the two-stage scoring pipeline.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {saved && <span className="text-xs text-emerald-400">Saved</span>}
          {isDirty && !saved && (
            <button
              onClick={() => data && setForm(data)}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              Reset
            </button>
          )}
          <button
            onClick={() => form && save.mutate(form)}
            disabled={save.isPending || !isDirty}
            className="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition"
          >
            {save.isPending ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {isLoading || !form ? (
        <p className="text-xs text-slate-600">Loading…</p>
      ) : (
        <div className="space-y-4">
          <div className="p-4 bg-slate-800/40 border border-slate-700/50 rounded-lg max-w-xs">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-3">
              Apply Threshold
            </p>
            {numInput("score_threshold", "Min score to verdict \"apply\" (1.0–10.0)", { step: "0.1", min: 1, max: 10 })}
            <p className="text-[11px] text-slate-600 mt-2">
              Jobs scoring at or above this are marked "apply" and trigger a Telegram notification.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Stage 1 */}
            <div className="space-y-3 p-4 bg-slate-800/40 border border-slate-700/50 rounded-lg">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
                Stage 1 — Filter Model
              </p>
              {textInput("filter_model", "Model ID", "e.g. google/gemini-2.5-flash-lite")}
              <div className="grid grid-cols-2 gap-3">
                {numInput("filter_model_price_in", "Input price ($/M tokens)")}
                {numInput("filter_model_price_out", "Output price ($/M tokens)")}
              </div>
            </div>

            {/* Stage 2 */}
            <div className="space-y-3 p-4 bg-slate-800/40 border border-slate-700/50 rounded-lg">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
                Stage 2 — Score Model
              </p>
              {textInput("score_model", "Model ID", "e.g. google/gemini-2.5-flash")}
              <div className="grid grid-cols-2 gap-3">
                {numInput("score_model_price_in", "Input price ($/M tokens)")}
                {numInput("score_model_price_out", "Output price ($/M tokens)")}
              </div>
              {numInput("score_model_cache_discount", "Cache discount multiplier (1.0 = no discount)")}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  const { user: me } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [daysBack, setDaysBack] = useState("1");
  const [lastResult, setLastResult] = useState<{ started: number; skipped: number } | null>(null);
  const [showCreateUser, setShowCreateUser] = useState(false);

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
      {showCreateUser && <CreateUserModal onClose={() => setShowCreateUser(false)} />}

      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Admin</h1>
          <p className="text-sm text-slate-500 mt-0.5">Click a user to view their scoring history</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCreateUser(true)}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-sm font-medium rounded-lg transition"
          >
            + Create User
          </button>
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

      {/* Model config */}
      <ModelConfigSection />

      {/* Users */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[600px]">
          <thead>
            <tr className="border-b border-slate-800 text-xs text-slate-500 uppercase tracking-wider">
              <th className="text-left px-5 py-3 font-medium">User</th>
              <th className="text-left px-5 py-3 font-medium hidden sm:table-cell">Joined</th>
              <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Last scoring</th>
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
