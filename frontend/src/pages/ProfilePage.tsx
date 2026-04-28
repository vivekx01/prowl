import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

// ---------------------------------------------------------------------------
// Resume upload card
// ---------------------------------------------------------------------------

function ResumeUpload({ onGenerated }: { onGenerated: (text: string) => void }) {
  const [status, setStatus] = useState<"idle" | "parsing" | "done" | "error">("idle");
  const [fileName, setFileName] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setStatus("parsing");
    setErrorMsg("");

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await api.post("/profile/parse-resume", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onGenerated(res.data.profile);
      setStatus("done");
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail ?? "Failed to parse resume");
      setStatus("error");
    }

    e.target.value = "";
  }

  return (
    <div className="card p-5 space-y-3">
      <div>
        <h2 className="text-sm font-medium text-slate-200">Import from Resume</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Upload a PDF and Prowl AI will generate your candidate profile automatically.
        </p>
      </div>

      <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleFile} />

      {status === "idle" || status === "error" ? (
        <button
          onClick={() => fileRef.current?.click()}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-dashed border-slate-700 hover:border-violet-500/50 hover:bg-violet-500/5 text-sm text-slate-400 hover:text-violet-300 transition-all"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
          Upload Resume PDF
        </button>
      ) : status === "parsing" ? (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-slate-800/50">
          <svg className="w-4 h-4 text-violet-400 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <div>
            <p className="text-sm text-slate-300">Parsing {fileName}…</p>
            <p className="text-xs text-slate-500">Generating your profile with AI</p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
            <svg className="w-4 h-4 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            <p className="text-sm text-emerald-300">Profile generated from {fileName}</p>
          </div>
          <button
            onClick={() => { setStatus("idle"); setFileName(""); }}
            className="w-full text-xs text-slate-500 hover:text-slate-300 transition-colors py-1"
          >
            Upload a different resume
          </button>
        </div>
      )}

      {status === "error" && (
        <p className="text-xs text-red-400 px-1">{errorMsg}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scrape settings card
// ---------------------------------------------------------------------------

function ScrapeSettings() {
  const qc = useQueryClient();
  const { data: settings = [] } = useQuery<{ key: string; value: string }[]>({
    queryKey: ["settings"],
    queryFn: () => api.get("/settings").then(r => r.data),
  });

  const [maxAge, setMaxAge] = useState("30");

  useEffect(() => {
    const s = settings.find(s => s.key === "max_job_age_days");
    if (s) setMaxAge(s.value);
  }, [settings]);

  const save = useMutation({
    mutationFn: () => api.put("/settings/max_job_age_days", { value: maxAge }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  return (
    <div className="card p-5 space-y-4">
      <h2 className="text-sm font-medium text-slate-200">Scrape Preferences</h2>

      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-300">Max job age</p>
          <p className="text-xs text-slate-500 mt-0.5">Listings older than this are skipped before any LLM call</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <input
            type="number"
            min={1}
            max={90}
            value={maxAge}
            onChange={e => setMaxAge(e.target.value)}
            className="input w-16 text-center"
          />
          <span className="text-sm text-slate-500">days</span>
        </div>
      </div>

      <div className="pt-1 border-t border-slate-800 flex justify-end">
        <button
          onClick={() => save.mutate()}
          disabled={save.isPending}
          className="btn-primary"
        >
          {save.isPending ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ProfilePage() {
  const qc = useQueryClient();

  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.get("/profile").then(r => r.data),
  });

  const [profileText, setProfileText] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (profile?.content && !dirty) setProfileText(profile.content);
  }, [profile]);

  const saveProfile = useMutation({
    mutationFn: () => api.put("/profile", { content: profileText }).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      setDirty(false);
    },
  });

  function handleGenerated(text: string) {
    setProfileText(text);
    setDirty(true);
  }

  return (
    <div className="w-full space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-slate-100">Profile</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Your candidate profile — used by the AI to evaluate every job listing.
        </p>
      </div>

      {/* 2-column layout: profile left, tools right */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-5 items-start">

        {/* Left — profile editor */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-medium text-slate-200">Candidate Profile</h2>
              <p className="text-xs text-slate-500 mt-0.5">Markdown supported. Be specific about your tech stack and seniority.</p>
            </div>
            <button
              onClick={() => saveProfile.mutate()}
              disabled={!dirty || saveProfile.isPending}
              className="btn-primary disabled:opacity-30 shrink-0"
            >
              {saveProfile.isPending ? "Saving…" : "Save profile"}
            </button>
          </div>
          <textarea
            value={profileText}
            onChange={e => { setProfileText(e.target.value); setDirty(true); }}
            rows={30}
            className="input font-mono text-xs leading-relaxed resize-y w-full"
            spellCheck={false}
            placeholder="Your candidate profile will appear here. Upload a resume or write manually."
          />
        </section>

        {/* Right — upload + settings */}
        <div className="space-y-4">
          <ResumeUpload onGenerated={handleGenerated} />
          <ScrapeSettings />
        </div>
      </div>
    </div>
  );
}
