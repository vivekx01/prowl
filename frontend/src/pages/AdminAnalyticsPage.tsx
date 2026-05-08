import { useMemo, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as echarts from "echarts";
import api from "../api/client";

// ---------------------------------------------------------------------------
// EChart wrapper
// ---------------------------------------------------------------------------

function EChart({ option, height = 280 }: { option: object; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    chart.current = echarts.init(ref.current, null, { renderer: "canvas" });
    const obs = new ResizeObserver(() => chart.current?.resize());
    obs.observe(ref.current);
    return () => { obs.disconnect(); chart.current?.dispose(); chart.current = null; };
  }, []);

  useEffect(() => {
    if (!chart.current) return;
    try { chart.current.setOption({ backgroundColor: "transparent", ...option }, true); } catch {}
  }, [option]);

  return <div ref={ref} style={{ height, width: "100%" }} />;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Summary {
  total_cost_usd: number;
  total_filter_cost_usd: number;
  total_score_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_filter_input_tokens: number;
  total_score_input_tokens: number;
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  cancelled_runs: number;
  total_matches: number;
  avg_matches_per_run: number;
}

interface DayPoint {
  date: string;
  cost_usd: number;
  filter_cost_usd: number;
  score_cost_usd: number;
  input_tokens: number;
  filter_input_tokens: number;
  score_input_tokens: number;
  output_tokens: number;
  runs: number;
  matches: number;
}

interface UserStat {
  user_id: number;
  email: string;
  name: string;
  cost_usd: number;
  filter_cost_usd: number;
  score_cost_usd: number;
  runs: number;
  matches: number;
  input_tokens: number;
}

interface Analytics {
  summary: Summary;
  daily: DayPoint[];
  by_user: UserStat[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtCost(v: number): string {
  if (v === 0) return "$0";
  if (v < 0.0001) return "<$0.0001";
  return `$${v.toFixed(4)}`;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
}

function fmtDay(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ---------------------------------------------------------------------------
// Shared chart style tokens
// ---------------------------------------------------------------------------

const GRID = { top: 36, right: 16, bottom: 40, left: 16, containLabel: true };
const AXIS_LINE = { lineStyle: { color: "#1e293b" } };
const SPLIT_LINE = { lineStyle: { color: "#1e293b", type: "dashed" as const, opacity: 0.6 } };
const AXIS_LABEL = { color: "#475569", fontSize: 11 };
const TOOLTIP_BASE = {
  backgroundColor: "#0f172a",
  borderColor: "#334155",
  borderWidth: 1,
  textStyle: { color: "#e2e8f0", fontSize: 12 },
  extraCssText: "box-shadow:0 8px 32px rgba(0,0,0,0.6);border-radius:10px;padding:10px 14px",
};
const LEGEND_BASE = {
  textStyle: { color: "#64748b", fontSize: 11 },
  icon: "circle",
  itemWidth: 8,
  itemHeight: 8,
  top: 4,
};

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  label, value, sub, accent = "slate",
}: {
  label: string; value: string; sub?: string; accent?: "violet" | "amber" | "emerald" | "slate" | "indigo";
}) {
  const valueColor: Record<string, string> = {
    violet: "text-violet-300",
    amber:  "text-amber-300",
    emerald: "text-emerald-300",
    indigo: "text-indigo-300",
    slate:  "text-slate-100",
  };
  const barColor: Record<string, string> = {
    violet: "bg-violet-500",
    amber:  "bg-amber-500",
    emerald: "bg-emerald-500",
    indigo: "bg-indigo-500",
    slate:  "bg-slate-600",
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl px-5 py-4 flex flex-col gap-2 relative overflow-hidden">
      <div className={`absolute top-0 left-0 w-full h-0.5 ${barColor[accent]}`} />
      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-semibold tabular-nums tracking-tight ${valueColor[accent]}`}>{value}</p>
      {sub && <p className="text-xs text-slate-600">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart panels
// ---------------------------------------------------------------------------

function ChartPanel({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-xl overflow-hidden ${className}`}>
      <div className="px-5 py-3.5 border-b border-slate-800/60">
        <p className="text-sm font-medium text-slate-300">{title}</p>
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const RANGE_OPTIONS = [
  { label: "7d",  value: 7  },
  { label: "30d", value: 30 },
  { label: "90d", value: 90 },
];

export default function AdminAnalyticsPage() {
  const [days, setDays] = useState(30);

  const { data, isLoading } = useQuery<Analytics>({
    queryKey: ["admin-analytics", days],
    queryFn: () => api.get(`/admin/analytics?days=${days}`).then((r) => r.data),
  });

  const s = data?.summary;
  const daily = data?.daily ?? [];
  const byUser = data?.by_user ?? [];

  const dates = daily.map((d) => d.date);
  const fmtDates = dates.map(fmtDay);
  const labelInterval = days === 7 ? 0 : days === 30 ? 4 : 13;

  // ── Cost over time ──────────────────────────────────────────────────────

  const costChartOption = useMemo(() => ({
    grid: GRID,
    tooltip: {
      ...TOOLTIP_BASE,
      trigger: "axis",
      formatter: (params: any[]) => {
        if (!params?.length) return "";
        const date = fmtDay(params[0].axisValue as string);
        let total = 0;
        const rows = params.map((p) => {
          total += (p.value as number) || 0;
          return `<div style="display:flex;justify-content:space-between;gap:20px;margin-top:3px">
            <span style="color:${p.color};display:flex;align-items:center;gap:5px">
              <span style="width:6px;height:6px;border-radius:50%;background:${p.color};display:inline-block"></span>
              ${p.seriesName}
            </span>
            <span style="color:#e2e8f0;font-weight:600">${fmtCost(p.value as number)}</span>
          </div>`;
        }).join("");
        return `<div style="font-weight:600;color:#94a3b8;font-size:11px;margin-bottom:4px">${date}</div>${rows}
          <div style="display:flex;justify-content:space-between;gap:20px;border-top:1px solid #1e293b;margin-top:6px;padding-top:6px">
            <span style="color:#64748b">Total</span>
            <span style="color:#f1f5f9;font-weight:700">${fmtCost(total)}</span>
          </div>`;
      },
    },
    legend: { ...LEGEND_BASE, data: ["Filter", "Score"] },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: AXIS_LINE,
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, interval: labelInterval, formatter: fmtDay },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: SPLIT_LINE,
      axisLabel: { ...AXIS_LABEL, formatter: (v: number) => v === 0 ? "$0" : `$${v.toFixed(4)}` },
    },
    series: [
      {
        name: "Filter",
        type: "line",
        stack: "cost",
        smooth: true,
        data: daily.map((d) => +(d.filter_cost_usd.toFixed(6))),
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(139,92,246,0.35)" },
            { offset: 1, color: "rgba(139,92,246,0.02)" },
          ]),
        },
        lineStyle: { color: "#8b5cf6", width: 2 },
        itemStyle: { color: "#8b5cf6" },
        symbolSize: 4,
        symbol: "circle",
        emphasis: { focus: "series" },
      },
      {
        name: "Score",
        type: "line",
        stack: "cost",
        smooth: true,
        data: daily.map((d) => +(d.score_cost_usd.toFixed(6))),
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(245,158,11,0.35)" },
            { offset: 1, color: "rgba(245,158,11,0.02)" },
          ]),
        },
        lineStyle: { color: "#f59e0b", width: 2 },
        itemStyle: { color: "#f59e0b" },
        symbolSize: 4,
        symbol: "circle",
        emphasis: { focus: "series" },
      },
    ],
  }), [daily, dates, labelInterval]);

  // ── Runs & Matches ──────────────────────────────────────────────────────

  const activityChartOption = useMemo(() => ({
    grid: GRID,
    tooltip: {
      ...TOOLTIP_BASE,
      trigger: "axis",
      formatter: (params: any[]) => {
        if (!params?.length) return "";
        const date = fmtDay(params[0].axisValue as string);
        const rows = params.map((p) =>
          `<div style="display:flex;justify-content:space-between;gap:20px;margin-top:3px">
            <span style="color:${p.color};display:flex;align-items:center;gap:5px">
              <span style="width:6px;height:6px;border-radius:50%;background:${p.color};display:inline-block"></span>
              ${p.seriesName}
            </span>
            <span style="color:#e2e8f0;font-weight:600">${p.value}</span>
          </div>`
        ).join("");
        return `<div style="font-weight:600;color:#94a3b8;font-size:11px;margin-bottom:4px">${date}</div>${rows}`;
      },
    },
    legend: { ...LEGEND_BASE, data: ["Runs", "Matches"] },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: AXIS_LINE,
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, interval: labelInterval, formatter: fmtDay },
    },
    yAxis: [
      { type: "value", axisLine: { show: false }, axisTick: { show: false }, splitLine: SPLIT_LINE, axisLabel: { ...AXIS_LABEL, formatter: (v: number) => `${v}` }, minInterval: 1 },
      { type: "value", axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false }, axisLabel: { ...AXIS_LABEL }, minInterval: 1 },
    ],
    series: [
      {
        name: "Runs",
        type: "bar",
        data: daily.map((d) => d.runs),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "#6366f1" },
            { offset: 1, color: "#4338ca" },
          ]),
          borderRadius: [3, 3, 0, 0],
        },
        barMaxWidth: 36,
        emphasis: { focus: "series" },
      },
      {
        name: "Matches",
        type: "line",
        yAxisIndex: 1,
        data: daily.map((d) => d.matches),
        smooth: true,
        lineStyle: { color: "#10b981", width: 2.5 },
        itemStyle: { color: "#10b981", borderWidth: 2, borderColor: "#0f172a" },
        symbolSize: 6,
        symbol: "circle",
        emphasis: { focus: "series" },
      },
    ],
  }), [daily, dates, labelInterval]);

  // ── Token usage ─────────────────────────────────────────────────────────

  const tokenChartOption = useMemo(() => ({
    grid: { ...GRID, bottom: 44 },
    tooltip: {
      ...TOOLTIP_BASE,
      trigger: "axis",
      formatter: (params: any[]) => {
        if (!params?.length) return "";
        const date = fmtDay(params[0].axisValue as string);
        let total = 0;
        const rows = params.filter((p) => (p.value as number) > 0).map((p) => {
          total += p.value as number;
          return `<div style="display:flex;justify-content:space-between;gap:20px;margin-top:3px">
            <span style="color:${p.color}">${p.seriesName}</span>
            <span style="color:#e2e8f0;font-weight:600">${fmtTokens(p.value as number)}</span>
          </div>`;
        }).join("");
        return `<div style="font-weight:600;color:#94a3b8;font-size:11px;margin-bottom:4px">${date}</div>${rows}
          <div style="display:flex;justify-content:space-between;gap:20px;border-top:1px solid #1e293b;margin-top:6px;padding-top:6px">
            <span style="color:#64748b">Total</span>
            <span style="color:#f1f5f9;font-weight:700">${fmtTokens(total)}</span>
          </div>`;
      },
    },
    legend: { ...LEGEND_BASE, data: ["Filter in", "Score in", "Output"] },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: AXIS_LINE,
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, interval: labelInterval, formatter: fmtDay },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: SPLIT_LINE,
      axisLabel: { ...AXIS_LABEL, formatter: fmtTokens },
    },
    series: [
      {
        name: "Filter in",
        type: "bar",
        stack: "tokens",
        data: daily.map((d) => d.filter_input_tokens),
        itemStyle: { color: "#8b5cf6" },
        barMaxWidth: 40,
        emphasis: { focus: "series" },
      },
      {
        name: "Score in",
        type: "bar",
        stack: "tokens",
        data: daily.map((d) => d.score_input_tokens),
        itemStyle: { color: "#f59e0b" },
        barMaxWidth: 40,
        emphasis: { focus: "series" },
      },
      {
        name: "Output",
        type: "bar",
        stack: "tokens",
        data: daily.map((d) => d.output_tokens),
        itemStyle: { color: "#334155", borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 40,
        emphasis: { focus: "series" },
      },
    ],
  }), [daily, dates, labelInterval]);

  // ── Cost split donut ────────────────────────────────────────────────────

  const donutOption = useMemo(() => {
    const fc = s?.total_filter_cost_usd ?? 0;
    const sc = s?.total_score_cost_usd ?? 0;
    const total = fc + sc;
    return {
      tooltip: {
        ...TOOLTIP_BASE,
        trigger: "item",
        formatter: (p: any) =>
          `<div style="font-weight:600;color:#e2e8f0">${p.name}</div>
           <div style="color:#94a3b8;margin-top:3px">${fmtCost(p.value)} · ${p.percent}%</div>`,
      },
      legend: { ...LEGEND_BASE, bottom: 8, left: "center" },
      graphic: total > 0 ? [{
        type: "group",
        left: "center",
        top: "38%",
        children: [
          {
            type: "text",
            style: {
              text: fmtCost(total),
              textAlign: "center",
              fill: "#e2e8f0",
              fontSize: 15,
              fontWeight: 700,
              x: 0, y: -10,
            },
          },
          {
            type: "text",
            style: {
              text: "total",
              textAlign: "center",
              fill: "#475569",
              fontSize: 11,
              x: 0, y: 10,
            },
          },
        ],
      }] : [],
      series: [{
        type: "pie",
        radius: ["52%", "74%"],
        center: ["50%", "44%"],
        data: [
          { value: +fc.toFixed(6), name: "Filter", itemStyle: { color: "#8b5cf6" } },
          { value: +sc.toFixed(6), name: "Score",  itemStyle: { color: "#f59e0b" } },
        ],
        label: { show: false },
        labelLine: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 12, shadowColor: "rgba(0,0,0,0.4)" },
          label: { show: true, formatter: "{b}\n{d}%", color: "#e2e8f0", fontSize: 12, fontWeight: 600 },
        },
      }],
    };
  }, [s]);

  // ── Per-user horizontal bar ─────────────────────────────────────────────

  const userChartOption = useMemo(() => {
    const sorted = [...byUser].slice(0, 8);
    const names = sorted.map((u) => u.name || u.email.split("@")[0]);
    return {
      grid: { top: 8, right: 80, bottom: 8, left: 16, containLabel: true },
      tooltip: {
        ...TOOLTIP_BASE,
        trigger: "axis",
        axisPointer: { type: "none" },
        formatter: (params: any[]) => {
          if (!params?.length) return "";
          const u = sorted[sorted.length - 1 - params[0].dataIndex];
          if (!u) return "";
          return `<div style="font-weight:600;color:#e2e8f0;margin-bottom:4px">${u.name || u.email}</div>
            <div style="color:#94a3b8;font-size:11px">${u.email}</div>
            <div style="margin-top:6px;display:flex;justify-content:space-between;gap:20px">
              <span style="color:#64748b">Cost</span>
              <span style="color:#e2e8f0;font-weight:600">${fmtCost(u.cost_usd)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;gap:20px;margin-top:2px">
              <span style="color:#64748b">Runs</span>
              <span style="color:#e2e8f0;font-weight:600">${u.runs}</span>
            </div>
            <div style="display:flex;justify-content:space-between;gap:20px;margin-top:2px">
              <span style="color:#64748b">Matches</span>
              <span style="color:#10b981;font-weight:600">${u.matches}</span>
            </div>`;
        },
      },
      xAxis: {
        type: "value",
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: SPLIT_LINE,
        axisLabel: { ...AXIS_LABEL, formatter: (v: number) => v === 0 ? "$0" : `$${v.toFixed(4)}` },
      },
      yAxis: {
        type: "category",
        data: [...names].reverse(),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { ...AXIS_LABEL, width: 90, overflow: "truncate" },
      },
      series: [{
        type: "bar",
        data: [...sorted].reverse().map((u) => +u.cost_usd.toFixed(6)),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
            { offset: 0, color: "#8b5cf6" },
            { offset: 1, color: "#6366f1" },
          ]),
          borderRadius: [0, 3, 3, 0],
        },
        label: {
          show: true,
          position: "right",
          color: "#475569",
          fontSize: 11,
          formatter: (p: any) => fmtCost(p.value as number),
        },
        barMaxWidth: 22,
        emphasis: { focus: "series" },
      }],
    };
  }, [byUser]);

  // ── Render ───────────────────────────────────────────────────────────────

  const userBarHeight = Math.max(200, Math.min(byUser.length, 8) * 40 + 20);

  return (
    <div className="w-full space-y-6">

      {/* Header + range picker */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Analytics</h1>
          <p className="text-sm text-slate-500 mt-0.5">Token usage and cost across all scoring runs</p>
        </div>
        <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1">
          {RANGE_OPTIONS.map((o) => (
            <button
              key={o.value}
              onClick={() => setDays(o.value)}
              className={`px-3.5 py-1.5 text-sm font-medium rounded-md transition-all ${
                days === o.value
                  ? "bg-violet-600 text-white shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl h-24 animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard
              label="Total Spent"
              value={fmtCost(s?.total_cost_usd ?? 0)}
              sub={`last ${days} days`}
              accent="amber"
            />
            <StatCard
              label="Filter Cost"
              value={fmtCost(s?.total_filter_cost_usd ?? 0)}
              sub={s && s.total_cost_usd > 0
                ? `${Math.round((s.total_filter_cost_usd / s.total_cost_usd) * 100)}% of total`
                : "—"}
              accent="violet"
            />
            <StatCard
              label="Score Cost"
              value={fmtCost(s?.total_score_cost_usd ?? 0)}
              sub={s && s.total_cost_usd > 0
                ? `${Math.round((s.total_score_cost_usd / s.total_cost_usd) * 100)}% of total`
                : "—"}
              accent="amber"
            />
            <StatCard
              label="Scoring Runs"
              value={`${s?.completed_runs ?? 0}`}
              sub={[
                s?.failed_runs    ? `${s.failed_runs} failed`    : "",
                s?.cancelled_runs ? `${s.cancelled_runs} cancelled` : "",
              ].filter(Boolean).join(" · ") || `${s?.total_runs ?? 0} total`}
              accent="indigo"
            />
            <StatCard
              label="Matches Found"
              value={`${s?.total_matches ?? 0}`}
              sub={`avg ${s?.avg_matches_per_run ?? 0} / run`}
              accent="emerald"
            />
          </div>

          {/* Token summary strip */}
          {(s?.total_input_tokens ?? 0) > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl px-5 py-3.5 flex items-center gap-6 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-violet-500" />
                <span className="text-xs text-slate-500">Filter in</span>
                <span className="text-sm font-semibold text-slate-200 tabular-nums">
                  {fmtTokens(s?.total_filter_input_tokens ?? 0)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                <span className="text-xs text-slate-500">Score in</span>
                <span className="text-sm font-semibold text-slate-200 tabular-nums">
                  {fmtTokens(s?.total_score_input_tokens ?? 0)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-600" />
                <span className="text-xs text-slate-500">Output</span>
                <span className="text-sm font-semibold text-slate-200 tabular-nums">
                  {fmtTokens(s?.total_output_tokens ?? 0)}
                </span>
              </div>
              <div className="ml-auto flex items-center gap-2 text-xs text-slate-600">
                <span>Total in</span>
                <span className="text-slate-400 font-semibold">{fmtTokens(s?.total_input_tokens ?? 0)}</span>
              </div>
            </div>
          )}

          {/* Cost over time + activity */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <ChartPanel title="Cost Over Time" className="lg:col-span-3">
              <EChart option={costChartOption} height={280} />
            </ChartPanel>
            <ChartPanel title="Runs & Matches" className="lg:col-span-2">
              <EChart option={activityChartOption} height={280} />
            </ChartPanel>
          </div>

          {/* Token usage */}
          <ChartPanel title="Token Usage">
            <EChart option={tokenChartOption} height={240} />
          </ChartPanel>

          {/* Donut + per-user */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <ChartPanel title="Cost Split" className="lg:col-span-2">
              <EChart option={donutOption} height={240} />
            </ChartPanel>
            <ChartPanel title="Usage by User" className="lg:col-span-3">
              {byUser.length === 0 ? (
                <div className="flex items-center justify-center h-40 text-slate-600 text-sm">No data</div>
              ) : (
                <EChart option={userChartOption} height={userBarHeight} />
              )}
            </ChartPanel>
          </div>

          {/* Per-user table */}
          {byUser.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-x-auto">
              <table className="w-full text-sm min-w-[560px]">
                <thead>
                  <tr className="border-b border-slate-800 text-xs text-slate-500 uppercase tracking-wider">
                    <th className="text-left px-5 py-3 font-medium">User</th>
                    <th className="text-right px-4 py-3 font-medium">Filter</th>
                    <th className="text-right px-4 py-3 font-medium">Score</th>
                    <th className="text-right px-4 py-3 font-medium">Total cost</th>
                    <th className="text-right px-4 py-3 font-medium">Runs</th>
                    <th className="text-right px-4 py-3 font-medium">Matches</th>
                    <th className="text-right px-5 py-3 font-medium">Tokens in</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {byUser.map((u) => (
                    <tr key={u.user_id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-5 py-3">
                        <p className="text-slate-200 font-medium">{u.name}</p>
                        <p className="text-xs text-slate-600">{u.email}</p>
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-violet-400/80 font-medium tabular-nums">
                        {fmtCost(u.filter_cost_usd)}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-amber-400/80 font-medium tabular-nums">
                        {fmtCost(u.score_cost_usd)}
                      </td>
                      <td className="px-4 py-3 text-right text-sm text-amber-400 font-semibold tabular-nums">
                        {fmtCost(u.cost_usd)}
                      </td>
                      <td className="px-4 py-3 text-right text-sm text-slate-300 tabular-nums">{u.runs}</td>
                      <td className="px-4 py-3 text-right text-sm text-emerald-400 font-medium tabular-nums">{u.matches}</td>
                      <td className="px-5 py-3 text-right text-xs text-slate-500 tabular-nums">
                        {fmtTokens(u.input_tokens)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
