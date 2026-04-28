import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

export default function SettingsPage() {
  const qc = useQueryClient();

  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.get("/profile").then(r => r.data),
  });

  const { data: settings = [] } = useQuery<{ key: string; value: string }[]>({
    queryKey: ["settings"],
    queryFn: () => api.get("/settings").then(r => r.data),
  });

  const [profileText, setProfileText] = useState("");
  const [maxAge, setMaxAge] = useState("30");
  const [profileDirty, setProfileDirty] = useState(false);

  useEffect(() => {
    if (profile?.content && !profileDirty) setProfileText(profile.content);
  }, [profile]);

  useEffect(() => {
    const s = settings.find(s => s.key === "max_job_age_days");
    if (s) setMaxAge(s.value);
  }, [settings]);

  const saveProfile = useMutation({
    mutationFn: () => api.put("/profile", { content: profileText }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      setProfileDirty(false);
    },
  });

  const saveSetting = useMutation({
    mutationFn: (kv: { key: string; value: string }) =>
      api.put(`/settings/${kv.key}`, { value: kv.value }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Settings</h1>
        <p className="text-sm text-slate-500 mt-0.5">Manage your profile and scrape preferences.</p>
      </div>

      {/* Profile */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium text-slate-200">Candidate Profile</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Used by the LLM to evaluate job fit. Markdown supported.
            </p>
          </div>
          <button
            onClick={() => saveProfile.mutate()}
            disabled={!profileDirty || saveProfile.isPending}
            className="btn-primary disabled:opacity-30"
          >
            {saveProfile.isPending ? "Saving…" : "Save"}
          </button>
        </div>
        <textarea
          value={profileText}
          onChange={e => { setProfileText(e.target.value); setProfileDirty(true); }}
          rows={22}
          className="input font-mono text-xs leading-relaxed resize-y"
          spellCheck={false}
        />
      </section>

      {/* Scrape settings */}
      <section className="card p-5 space-y-4">
        <h2 className="text-sm font-medium text-slate-200">Scrape Settings</h2>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-300">Max job age</p>
            <p className="text-xs text-slate-500 mt-0.5">
              Jobs older than this are skipped before any LLM call
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              max={90}
              value={maxAge}
              onChange={e => setMaxAge(e.target.value)}
              className="input w-20 text-center"
            />
            <span className="text-sm text-slate-500">days</span>
          </div>
        </div>

        <div className="flex justify-end pt-1 border-t border-slate-800">
          <button
            onClick={() => saveSetting.mutate({ key: "max_job_age_days", value: maxAge })}
            className="btn-primary"
          >
            {saveSetting.isPending ? "Saving…" : "Save settings"}
          </button>
        </div>
      </section>
    </div>
  );
}
