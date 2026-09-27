import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import api, { type ApiKeyInfo } from "../api/client";
import { STATUS_OPTIONS } from "./JobsPage";
import { IconCheck, IconCopy } from "../components/Icons";

// ---------------------------------------------------------------------------
// Markdown guide
// ---------------------------------------------------------------------------

function buildGuide(baseUrl: string): string {
  const statusList = STATUS_OPTIONS.map(s => `\`${s}\``).join(", ");
  return `
## Authentication

Every request needs an API key in the \`X-API-Key\` header. Generate one from the panel on the right — you can mint a separate key per bot or script, and revoke any single one without affecting the others.

\`\`\`bash
export PROWL_URL="${baseUrl}"
export API_KEY="YOUR_API_KEY"
\`\`\`

## 1. Get recommended jobs

\`GET /api/jobs\`

Returns your scored job matches — title, apply URL, the portal it's hosted on (\`workday\`, \`greenhouse\`, \`lever\`, \`oracle_hcm\`), the AI score/verdict, and the current application status.

**Query parameters**

| Param | Description |
|---|---|
| \`verdict\` | \`apply\` or \`skip\` — the AI's recommendation. Jobs verdicted \`apply\` already scored above the configured threshold. |
| \`company_id\` | Restrict to one company |
| \`search\` | Search by job title or company name |
| \`page\`, \`page_size\` | Pagination — default 50/page |

**Request**

\`\`\`bash
curl "$PROWL_URL/api/jobs?verdict=apply" \\
  -H "X-API-Key: $API_KEY"
\`\`\`

**Response** (truncated)

\`\`\`json
{
  "total": 1,
  "items": [
    {
      "id": 4821,
      "title": "Senior Backend Engineer",
      "company_name": "Acme Corp",
      "platform": "greenhouse",
      "url": "https://boards.greenhouse.io/acme/jobs/12345",
      "location": "Remote",
      "score": { "score": 8.7, "verdict": "apply", "reason": "..." },
      "application": null
    }
  ]
}
\`\`\`

If \`application\` is \`null\`, the job isn't tracked yet — use **POST** below. If it's an object, use **PATCH** with its \`id\`.

## 2. Mark a job as applied

Which endpoint you call depends on whether the job already has an \`application\` record.

**Not tracked yet — POST**

\`\`\`bash
curl -X POST "$PROWL_URL/api/applications" \\
  -H "X-API-Key: $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"listing_id": 4821, "status": "applied"}'
\`\`\`

**Already tracked — PATCH**

\`\`\`bash
curl -X PATCH "$PROWL_URL/api/applications/<application_id>" \\
  -H "X-API-Key: $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"status": "applied"}'
\`\`\`

Supported \`status\` values: ${statusList}. \`applied_at\` is set automatically the moment status becomes \`applied\` — don't send it yourself.

## Suggested bot loop

1. \`GET /api/jobs?verdict=apply\`, then filter to items where \`application\` is \`null\` or \`application.status\` is \`"saved"\`.
2. For each match, open \`url\` and submit the application on the portal.
3. Call \`POST /api/applications\` (or \`PATCH\` if it's already tracked) with \`status: "applied"\`.

## Scope & security

- A key only works on the two endpoints above — it can't reach account settings, admin routes, or trigger a scrape.
- Keys are shown in full exactly once, at creation. Only a prefix is stored afterward for identification.
- Revoke a key any time from the list on the right; it stops working immediately.
`.trim();
}

// ---------------------------------------------------------------------------
// Markdown rendering (dark-theme styled)
// ---------------------------------------------------------------------------

const mdComponents = {
  h2: ({ children }: any) => (
    <h2 className="text-sm font-semibold text-slate-100 mt-6 first:mt-0 pb-1.5 border-b border-slate-800">{children}</h2>
  ),
  h3: ({ children }: any) => (
    <h3 className="text-xs font-semibold text-slate-200 mt-4">{children}</h3>
  ),
  p: ({ children }: any) => (
    <p className="text-xs text-slate-400 leading-relaxed">{children}</p>
  ),
  ol: ({ children }: any) => (
    <ol className="list-decimal pl-4 space-y-1 text-xs text-slate-400 leading-relaxed">{children}</ol>
  ),
  ul: ({ children }: any) => (
    <ul className="list-disc pl-4 space-y-1 text-xs text-slate-400 leading-relaxed">{children}</ul>
  ),
  li: ({ children }: any) => <li>{children}</li>,
  strong: ({ children }: any) => <strong className="text-slate-200 font-medium">{children}</strong>,
  a: ({ children, href }: any) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-violet-400 hover:text-violet-300 transition-colors">
      {children}
    </a>
  ),
  code: ({ className, children }: any) => {
    // block code (inside <pre>) has a language className; inline code doesn't
    if (className) {
      return <code className={className}>{children}</code>;
    }
    return (
      <code className="text-violet-300 bg-slate-800/80 rounded px-1 py-0.5 text-[11px] font-mono">
        {children}
      </code>
    );
  },
  pre: ({ children }: any) => (
    <pre className="text-[11px] font-mono text-slate-300 bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2.5 overflow-x-auto my-2">
      {children}
    </pre>
  ),
  table: ({ children }: any) => (
    <div className="overflow-x-auto my-2">
      <table className="w-full text-xs border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }: any) => <thead className="border-b border-slate-800">{children}</thead>,
  th: ({ children }: any) => (
    <th className="text-left text-slate-300 font-medium px-2.5 py-1.5 whitespace-nowrap">{children}</th>
  ),
  td: ({ children }: any) => (
    <td className="text-slate-400 px-2.5 py-1.5 align-top border-t border-slate-800/60">{children}</td>
  ),
};

function ApiGuide() {
  const baseUrl = typeof window !== "undefined" ? window.location.origin : "https://your-prowl-url";
  const markdown = useMemo(() => buildGuide(baseUrl), [baseUrl]);
  const [copied, setCopied] = useState(false);

  async function copyGuide() {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable — user can still select the text manually
    }
  }

  return (
    <div className="card p-5 space-y-1">
      <div className="flex items-center justify-end -mt-1 -mr-1 mb-2">
        <button onClick={copyGuide} className="btn-ghost text-xs px-2.5 py-1 flex items-center gap-1.5">
          {copied ? (
            <>
              <IconCheck className="w-3.5 h-3.5 text-emerald-400" />
              Copied!
            </>
          ) : (
            <>
              <IconCopy className="w-3.5 h-3.5" />
              Copy guide
            </>
          )}
        </button>
      </div>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Key management
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function KeyRow({ apiKey, onRevoke, revoking }: { apiKey: ApiKeyInfo; onRevoke: () => void; revoking: boolean }) {
  return (
    <div className="flex items-start justify-between gap-2 py-2.5 border-b border-slate-800/60 last:border-b-0">
      <div className="min-w-0">
        <p className="text-xs font-medium text-slate-200 truncate">{apiKey.label || "Unnamed key"}</p>
        <p className="text-[11px] font-mono text-slate-500 mt-0.5">{apiKey.key_prefix}…</p>
        <p className="text-[11px] text-slate-600 mt-0.5">
          Created {formatDate(apiKey.created_at)}
          {apiKey.last_used_at && <> · last used {formatDate(apiKey.last_used_at)}</>}
        </p>
      </div>
      <button
        onClick={onRevoke}
        disabled={revoking}
        className="btn-ghost text-xs text-red-400 hover:text-red-300 shrink-0"
      >
        Revoke
      </button>
    </div>
  );
}

function ApiKeyManager() {
  const qc = useQueryClient();
  const [label, setLabel] = useState("");
  const [freshKey, setFreshKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: keys = [], isLoading } = useQuery<ApiKeyInfo[]>({
    queryKey: ["api-keys"],
    queryFn: () => api.get("/api-keys").then(r => r.data),
  });

  const generate = useMutation({
    mutationFn: (label: string) => api.post("/api-keys/generate", { label }).then(r => r.data),
    onSuccess: (data) => {
      setFreshKey(data.api_key);
      setCopied(false);
      setLabel("");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: number) => api.delete(`/api-keys/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  async function copyKey() {
    if (!freshKey) return;
    try {
      await navigator.clipboard.writeText(freshKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable — user can still select the text manually
    }
  }

  return (
    <div className="card p-5 space-y-4">
      <div>
        <h2 className="text-sm font-medium text-slate-200">Your keys</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          One key per bot or script — name it so you remember what it's for.
        </p>
      </div>

      <div className="flex gap-2">
        <input
          value={label}
          onChange={e => setLabel(e.target.value)}
          placeholder="e.g. Application bot"
          className="input flex-1 text-sm"
          onKeyDown={e => { if (e.key === "Enter" && label.trim()) generate.mutate(label.trim()); }}
        />
        <button
          onClick={() => generate.mutate(label.trim())}
          disabled={generate.isPending}
          className="btn-primary text-sm shrink-0"
        >
          {generate.isPending ? "Generating…" : "Generate"}
        </button>
      </div>

      {freshKey && (
        <div className="space-y-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <p className="text-xs text-amber-300">
            Copy this key now — it won't be shown again.
          </p>
          <div className="flex gap-2">
            <code className="flex-1 text-xs font-mono text-slate-200 bg-slate-900/60 rounded-md px-2.5 py-1.5 overflow-x-auto whitespace-nowrap">
              {freshKey}
            </code>
            <button onClick={copyKey} className="btn-secondary text-xs px-2.5 shrink-0">
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        </div>
      )}

      <div>
        {isLoading ? (
          <p className="text-xs text-slate-600">Loading…</p>
        ) : keys.length === 0 ? (
          <p className="text-xs text-slate-600">No API keys yet. Generate one above.</p>
        ) : (
          keys.map(k => (
            <KeyRow
              key={k.id}
              apiKey={k}
              onRevoke={() => revoke.mutate(k.id)}
              revoking={revoke.isPending && revoke.variables === k.id}
            />
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ApiAccessPage() {
  return (
    <div className="w-full space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-slate-100">API Access</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Let a script or bot read your recommended jobs and track applications on your behalf.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-5 items-start">
        <ApiGuide />
        <ApiKeyManager />
      </div>
    </div>
  );
}
