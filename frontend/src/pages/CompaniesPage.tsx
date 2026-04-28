import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { type Company } from "../api/client";
import Modal from "../components/Modal";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PLATFORM_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  workday:  { bg: "bg-blue-500/10",   text: "text-blue-400",   dot: "bg-blue-500" },
  linkedin: { bg: "bg-sky-500/10",    text: "text-sky-400",    dot: "bg-sky-500" },
  naukri:   { bg: "bg-orange-500/10", text: "text-orange-400", dot: "bg-orange-500" },
};

function PlatformBadge({ platform }: { platform: string }) {
  const c = PLATFORM_COLORS[platform] ?? { bg: "bg-slate-800", text: "text-slate-400", dot: "bg-slate-500" };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {platform}
    </span>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent
        transition-colors duration-200 focus:outline-none
        ${on ? "bg-violet-600" : "bg-slate-700"}`}
      role="switch"
      aria-checked={on}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200
          ${on ? "translate-x-4" : "translate-x-0"}`}
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// CSV helpers (shared by export + import)
// ---------------------------------------------------------------------------

function parseCsvLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') { current += '"'; i++; }
      else inQuotes = !inQuotes;
    } else if (ch === ',' && !inQuotes) {
      result.push(current); current = "";
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
}

function parseCsv(text: string): Record<string, string>[] {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).filter(l => l.trim()).map(line => {
    const vals = parseCsvLine(line);
    return Object.fromEntries(headers.map((h, i) => [h.trim(), vals[i] ?? ""]));
  });
}

// ---------------------------------------------------------------------------
// CSV export
// ---------------------------------------------------------------------------

function exportCsv(companies: Company[], platform: string | null) {
  const rows = platform ? companies.filter(c => c.platform === platform) : companies;
  const escape = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = [
    ["name", "platform", "active", "config"].join(","),
    ...rows.map(c => [
      escape(c.name),
      escape(c.platform),
      escape(c.active),
      escape(JSON.stringify(c.config)),
    ].join(",")),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `companies${platform ? `_${platform}` : ""}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function ExportButton({ companies, platforms }: { companies: Company[]; platforms: string[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const options: { label: string; value: string | null }[] = [
    { label: "All platforms", value: null },
    ...platforms.map(p => ({ label: p.charAt(0).toUpperCase() + p.slice(1), value: p })),
  ];

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className="btn-ghost flex items-center gap-1.5"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        Export
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 card shadow-2xl overflow-hidden min-w-[170px]">
            <p className="px-3 py-2 text-xs text-slate-500 border-b border-slate-800">Export as CSV</p>
            {options.map(o => (
              <button
                key={String(o.value)}
                onClick={() => { exportCsv(companies, o.value); setOpen(false); }}
                className="w-full text-left px-3 py-2 text-sm text-slate-300 hover:bg-slate-800 transition-colors flex items-center gap-2"
              >
                {o.value && (
                  <span className={`w-2 h-2 rounded-full ${PLATFORM_COLORS[o.value]?.dot ?? "bg-slate-500"}`} />
                )}
                {o.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CSV import
// ---------------------------------------------------------------------------

type ParsedRow = Record<string, string> & { _status: "new" | "exists" };

function ImportButton({ existing }: { existing: Company[] }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<ParsedRow[]>([]);
  const [fileName, setFileName] = useState("");
  const [result, setResult] = useState<{ imported: number; skipped: number; errors: string[] } | null>(null);

  const existingNames = new Set(existing.map(c => c.name.toLowerCase()));

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setResult(null);
    const reader = new FileReader();
    reader.onload = ev => {
      const parsed = parseCsv(ev.target?.result as string);
      const tagged: ParsedRow[] = parsed.map(r => ({
        ...r,
        _status: existingNames.has((r.name ?? "").toLowerCase()) ? "exists" : "new",
      }));
      setRows(tagged);
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  const doImport = useMutation({
    mutationFn: () => {
      const toImport = rows
        .filter(r => r._status === "new")
        .map(({ _status, ...r }) => {
          // Support both new format (config column) and legacy Workday CSV columns
          let config: Record<string, string> = {};
          if (r.config) {
            try { config = JSON.parse(r.config); } catch { config = {}; }
          } else {
            if (r.listing_endpoint) config.listing_endpoint = r.listing_endpoint;
            if (r.jd_base) config.jd_base = r.jd_base;
            if (r.base_careers_url) config.base_careers_url = r.base_careers_url;
            if (r.payload) config.payload = r.payload;
          }
          return {
            name: r.name ?? "",
            platform: r.platform || "workday",
            active: r.active !== "false",
            config,
          };
        });
      return api.post("/companies/bulk", { companies: toImport }).then(r => r.data);
    },
    onSuccess: data => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      setResult(data);
    },
  });

  const newCount = rows.filter(r => r._status === "new").length;
  const existsCount = rows.filter(r => r._status === "exists").length;
  const open = rows.length > 0;

  return (
    <>
      <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleFile} />

      <button
        onClick={() => fileRef.current?.click()}
        className="btn-ghost flex items-center gap-1.5"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
        </svg>
        Import
      </button>

      <Modal open={open} onClose={() => { setRows([]); setResult(null); }} title={`Import · ${fileName}`} width="max-w-2xl">
        {result ? (
          <div className="space-y-4">
            <div className="flex gap-4">
              <div className="flex-1 card p-4 text-center">
                <p className="text-2xl font-bold text-emerald-400">{result.imported}</p>
                <p className="text-xs text-slate-500 mt-1">imported</p>
              </div>
              <div className="flex-1 card p-4 text-center">
                <p className="text-2xl font-bold text-slate-400">{result.skipped}</p>
                <p className="text-xs text-slate-500 mt-1">already existed</p>
              </div>
            </div>
            {result.errors.length > 0 && (
              <div className="card p-3 space-y-1">
                <p className="text-xs font-medium text-red-400">Errors</p>
                {result.errors.map((e, i) => (
                  <p key={i} className="text-xs text-slate-500 font-mono">{e}</p>
                ))}
              </div>
            )}
            <div className="flex justify-end pt-2 border-t border-slate-800">
              <button onClick={() => { setRows([]); setResult(null); }} className="btn-primary">Done</button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary */}
            <div className="flex items-center gap-3 text-sm">
              <span className="text-slate-300">{rows.length} rows found</span>
              <span className="text-emerald-400">{newCount} new</span>
              {existsCount > 0 && <span className="text-slate-500">{existsCount} already exist (will be skipped)</span>}
            </div>

            {/* Preview table */}
            <div className="card overflow-hidden">
              <div className="overflow-y-auto max-h-72">
                <table className="w-full text-xs">
                  <thead className="bg-slate-800/60 border-b border-slate-800">
                    <tr>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Name</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium">Platform</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium hidden sm:table-cell">Endpoint</th>
                      <th className="text-left px-3 py-2 text-slate-500 font-medium w-20">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {rows.map((r, i) => (
                      <tr key={i} className={r._status === "exists" ? "opacity-40" : ""}>
                        <td className="px-3 py-2 text-slate-200 font-medium">{r.name}</td>
                        <td className="px-3 py-2">
                          <PlatformBadge platform={r.platform || "workday"} />
                        </td>
                        <td className="px-3 py-2 text-slate-500 font-mono truncate max-w-xs hidden sm:table-cell">
                          {r.listing_endpoint || r.config || "—"}
                        </td>
                        <td className="px-3 py-2">
                          {r._status === "new" ? (
                            <span className="text-emerald-400">new</span>
                          ) : (
                            <span className="text-slate-600">exists</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
              <button onClick={() => setRows([])} className="btn-ghost">Cancel</button>
              <button
                onClick={() => doImport.mutate()}
                disabled={newCount === 0 || doImport.isPending}
                className="btn-primary"
              >
                {doImport.isPending ? "Importing…" : `Import ${newCount} companies`}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}

// ---------------------------------------------------------------------------
// Company card row
// ---------------------------------------------------------------------------

function CompanyCard({
  company,
  onEdit,
}: {
  company: Company;
  onEdit: (c: Company) => void;
}) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const toggle = useMutation({
    mutationFn: () =>
      api.patch(`/companies/${company.id}`, { active: !company.active }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  const remove = useMutation({
    mutationFn: () => api.delete(`/companies/${company.id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  const initial = company.name.charAt(0).toUpperCase();

  return (
    <div className={`card transition-all ${company.active ? "" : "opacity-60"}`}>
      <div className="flex items-center gap-4 px-4 py-3.5">
        {/* Avatar */}
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-slate-700 to-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
          <span className="text-sm font-bold text-slate-300">{initial}</span>
        </div>

        {/* Name + endpoint */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-slate-100 truncate">{company.name}</p>
            <PlatformBadge platform={company.platform} />
          </div>
          <p className="text-xs text-slate-600 font-mono truncate mt-0.5">
            {company.config?.listing_endpoint ?? Object.values(company.config ?? {})[0] ?? ""}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-4 shrink-0">
          <Toggle on={company.active} onChange={() => toggle.mutate()} />

          <button
            onClick={() => onEdit(company)}
            className="text-slate-600 hover:text-slate-300 transition-colors"
            title="Edit"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
            </svg>
          </button>

          <button
            onClick={() => setExpanded(e => !e)}
            className="text-slate-600 hover:text-slate-300 transition-colors"
            title="Details"
          >
            <svg className={`w-4 h-4 transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          <button
            onClick={() => confirm(`Delete ${company.name}?`) && remove.mutate()}
            className="text-slate-600 hover:text-red-400 transition-colors"
            title="Delete"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
          </button>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-slate-800 px-4 py-3 grid grid-cols-2 gap-x-6 gap-y-3">
          {Object.entries(company.config ?? {}).map(([key, val]) => val ? (
            <div key={key} className="col-span-2">
              <p className="text-xs text-slate-600 mb-0.5 capitalize">{key.replace(/_/g, " ")}</p>
              <p className="text-xs text-slate-400 font-mono break-all">{String(val)}</p>
            </div>
          ) : null)}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-platform field definitions
// ---------------------------------------------------------------------------

interface FieldDef {
  key: string;
  label: string;
  placeholder: string;
  required?: boolean;
  multiline?: boolean;
  hint?: string;
}

const PLATFORM_FIELDS: Record<string, FieldDef[]> = {
  workday: [
    { key: "listing_endpoint", label: "Listing API endpoint", placeholder: "https://company.wd1.myworkdayjobs.com/wday/cxs/…/jobs", required: true },
    { key: "jd_base",          label: "JD base URL",          placeholder: "https://company.wd1.myworkdayjobs.com/wday/cxs/…" },
    { key: "base_careers_url", label: "Careers page URL",      placeholder: "https://company.wd1.myworkdayjobs.com/en-US/…" },
    { key: "payload",          label: "Payload",               placeholder: "{}", multiline: true, hint: "JSON body sent with the listing POST request" },
  ],
};

function getFields(platform: string): FieldDef[] {
  return PLATFORM_FIELDS[platform] ?? [
    { key: "listing_endpoint", label: "Listing endpoint", placeholder: "https://…", required: true },
  ];
}

// ---------------------------------------------------------------------------
// Shared form body (used by both add + edit modals)
// ---------------------------------------------------------------------------

function CompanyForm({
  form,
  platforms,
  set,
  onCancel,
  onSubmit,
  isPending,
  submitLabel,
}: {
  form: Record<string, string>;
  platforms: string[];
  set: (k: string, v: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
  isPending: boolean;
  submitLabel: string;
}) {
  const fields = getFields(form.platform);
  const requiredKey = fields.find(f => f.required)?.key;
  const valid = form.name.trim() && (!requiredKey || form[requiredKey]?.trim());

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-slate-400">Company name *</label>
          <input
            value={form.name}
            onChange={e => set("name", e.target.value)}
            placeholder="Acme Corp"
            className="input"
            autoFocus
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-slate-400">Portal / Scraper *</label>
          <select
            value={form.platform}
            onChange={e => set("platform", e.target.value)}
            className="input appearance-none cursor-pointer"
          >
            {platforms.map(p => (
              <option key={p} value={p} className="bg-slate-900 capitalize">{p}</option>
            ))}
          </select>
        </div>
      </div>

      {fields.map(({ key, label, placeholder, required, multiline, hint }) =>
        multiline ? (
          <div key={key} className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">
              {label} {hint && <span className="text-slate-600 font-normal">{hint}</span>}
            </label>
            <textarea
              value={form[key] ?? ""}
              onChange={e => set(key, e.target.value)}
              placeholder={placeholder}
              rows={4}
              className="input font-mono text-xs resize-none"
              spellCheck={false}
            />
          </div>
        ) : (
          <div key={key} className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400">
              {label} {required && <span className="text-slate-600">*</span>}
            </label>
            <input
              value={form[key] ?? ""}
              onChange={e => set(key, e.target.value)}
              placeholder={placeholder}
              className="input font-mono text-xs"
            />
          </div>
        )
      )}

      <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
        <button onClick={onCancel} className="btn-ghost">Cancel</button>
        <button
          onClick={onSubmit}
          disabled={!valid || isPending}
          className="btn-primary"
        >
          {isPending ? "Saving…" : submitLabel}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add company modal
// ---------------------------------------------------------------------------

const EMPTY: Record<string, string> = { name: "", platform: "workday" };

function buildPayload(form: Record<string, string>) {
  const { name, platform, ...rest } = form;
  return { name, platform, active: true, config: rest };
}

function AddCompanyModal({
  open,
  onClose,
  platforms,
}: {
  open: boolean;
  onClose: () => void;
  platforms: string[];
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ ...EMPTY });
  const set = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));

  const create = useMutation({
    mutationFn: () => api.post("/companies", buildPayload(form)).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      setForm({ ...EMPTY });
      onClose();
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="Add company" width="max-w-xl">
      <CompanyForm
        form={form}
        platforms={platforms}
        set={set}
        onCancel={onClose}
        onSubmit={() => create.mutate()}
        isPending={create.isPending}
        submitLabel="Add company"
      />
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Edit company modal
// ---------------------------------------------------------------------------

function EditCompanyModal({
  company,
  onClose,
  platforms,
}: {
  company: Company;
  onClose: () => void;
  platforms: string[];
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({
    name: company.name,
    platform: company.platform,
    ...(company.config ?? {}),
  });
  const set = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));

  const update = useMutation({
    mutationFn: () => api.patch(`/companies/${company.id}`, buildPayload(form)).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      onClose();
    },
  });

  return (
    <Modal open onClose={onClose} title={`Edit · ${company.name}`} width="max-w-xl">
      <CompanyForm
        form={form}
        platforms={platforms}
        set={set}
        onCancel={onClose}
        onSubmit={() => update.mutate()}
        isPending={update.isPending}
        submitLabel="Save changes"
      />
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function CompaniesPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Company | null>(null);
  const [filter, setFilter] = useState<"all" | "active" | "paused">("all");
  const [search, setSearch] = useState("");

  const { data: companies = [] } = useQuery<Company[]>({
    queryKey: ["companies"],
    queryFn: () => api.get("/companies").then(r => r.data),
  });

  const { data: platforms = ["workday"] } = useQuery<string[]>({
    queryKey: ["platforms"],
    queryFn: () => api.get("/companies/platforms").then(r => r.data),
  });

  const q = search.trim().toLowerCase();
  const filtered = companies.filter(c => {
    if (filter === "active" && !c.active) return false;
    if (filter === "paused" && c.active) return false;
    if (q && !c.name.toLowerCase().includes(q)) return false;
    return true;
  });

  const activeCount = companies.filter(c => c.active).length;

  return (
    <div className="w-full space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Companies</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {activeCount} active · {companies.length - activeCount} paused
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ImportButton existing={companies} />
          <ExportButton companies={companies} platforms={platforms} />
          <button onClick={() => setModalOpen(true)} className="btn-primary flex items-center gap-1.5">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Add company
          </button>
        </div>
      </div>

      {/* Search + filter row */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z" />
          </svg>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search companies…"
            className="input pl-8 text-sm h-8"
          />
        </div>

        {/* Filter tabs */}
        <div className="flex rounded-lg border border-slate-800 overflow-hidden w-fit">
        {(["all", "active", "paused"] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 text-xs font-medium capitalize transition-colors ${
              filter === f
                ? "bg-slate-800 text-slate-100"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {f}
          </button>
        ))}
        </div>
      </div>

      {/* List */}
      {filtered.length === 0 ? (
        <div className="card p-12 text-center">
          <p className="text-slate-400 font-medium">No companies</p>
          <p className="text-sm text-slate-600 mt-1">Add one to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(c => (
            <CompanyCard key={c.id} company={c} onEdit={setEditTarget} />
          ))}
        </div>
      )}

      <AddCompanyModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        platforms={platforms}
      />

      {editTarget && (
        <EditCompanyModal
          company={editTarget}
          onClose={() => setEditTarget(null)}
          platforms={platforms}
        />
      )}
    </div>
  );
}
