import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import api from "../api/client";

interface ScoreResult {
  score: number;
  verdict: "apply" | "skip";
  reason: string;
}

function ScoreDisplay({ result }: { result: ScoreResult }) {
  const isApply = result.verdict === "apply";

  const scoreColor =
    result.score >= 7
      ? "text-emerald-400"
      : result.score >= 5
      ? "text-amber-400"
      : "text-red-400";

  const scoreRingColor =
    result.score >= 7
      ? "border-emerald-500/40"
      : result.score >= 5
      ? "border-amber-500/40"
      : "border-red-500/40";

  const scoreBg =
    result.score >= 7
      ? "bg-emerald-500/5"
      : result.score >= 5
      ? "bg-amber-500/5"
      : "bg-red-500/5";

  return (
    <div className="card p-6 space-y-5">
      <div className="flex items-center gap-5">
        {/* Score ring */}
        <div className={`w-20 h-20 rounded-full border-2 ${scoreRingColor} ${scoreBg} flex flex-col items-center justify-center shrink-0`}>
          <span className={`text-2xl font-bold ${scoreColor}`}>{result.score.toFixed(1)}</span>
          <span className="text-xs text-slate-600">/10</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                isApply
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "bg-red-500/10 text-red-400"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isApply ? "bg-emerald-400" : "bg-red-400"
                }`}
              />
              {isApply ? "Apply" : "Skip"}
            </span>
          </div>
          <p className="text-sm text-slate-300 leading-relaxed">{result.reason}</p>
        </div>
      </div>

      {/* Score bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs text-slate-600">
          <span>Poor fit</span>
          <span>Strong fit</span>
        </div>
        <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              result.score >= 7
                ? "bg-emerald-500"
                : result.score >= 5
                ? "bg-amber-500"
                : "bg-red-500"
            }`}
            style={{ width: `${(result.score / 10) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}

export default function CheckJDPage() {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [description, setDescription] = useState("");

  const score = useMutation<ScoreResult, Error, void>({
    mutationFn: () =>
      api.post("/score-jd", { title, company, description }).then(r => r.data),
  });

  const canSubmit = description.trim().length > 50;

  return (
    <div className="w-full space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Check a JD</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Paste any job description and score it against your profile.
          </p>
        </div>
        <button
          onClick={() => { setTitle(""); setCompany(""); setDescription(""); score.reset(); }}
          className="btn-ghost text-xs"
          disabled={!title && !company && !description}
        >
          Clear
        </button>
      </div>

      <div className="grid grid-cols-2 gap-5 items-start">
        {/* Left — input */}
        <div className="card p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-400">Job title</label>
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="e.g. Senior Backend Engineer"
                className="input"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-400">Company</label>
              <input
                value={company}
                onChange={e => setCompany(e.target.value)}
                placeholder="e.g. Acme Corp"
                className="input"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">
              Job description <span className="text-slate-600">*</span>
            </label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Paste the full job description here…"
              rows={22}
              className="input resize-none font-mono text-xs leading-relaxed"
              spellCheck={false}
            />
            {description.trim().length > 0 && description.trim().length <= 50 && (
              <p className="text-xs text-slate-600">Paste more of the JD for a useful score.</p>
            )}
          </div>

          <div className="flex justify-end pt-1 border-t border-slate-800">
            <button
              onClick={() => score.mutate()}
              disabled={!canSubmit || score.isPending}
              className="btn-primary flex items-center gap-2"
            >
              {score.isPending ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Scoring…
                </>
              ) : (
                "Score JD"
              )}
            </button>
          </div>
        </div>

        {/* Right — result */}
        <div>
          {score.isError && (
            <div className="card p-4 border border-red-900/40 bg-red-500/5">
              <p className="text-sm text-red-400">
                {(score.error as any)?.response?.data?.detail ?? score.error.message}
              </p>
            </div>
          )}

          {score.data ? (
            <ScoreDisplay result={score.data} />
          ) : (
            <div className="card p-10 flex flex-col items-center justify-center text-center gap-2 border-dashed">
              <p className="text-slate-500 text-sm">Score will appear here</p>
              <p className="text-slate-700 text-xs">Paste a JD and hit Score JD</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
