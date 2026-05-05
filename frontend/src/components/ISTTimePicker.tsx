import { useState } from "react";

const IST_OFFSET = 330; // UTC+5:30 in minutes

export function utcToIst(utcTime: string): string {
  const [h, m] = utcTime.split(":").map(Number);
  const total = ((h * 60 + m + IST_OFFSET) % 1440 + 1440) % 1440;
  const h24 = Math.floor(total / 60);
  const min = total % 60;
  const ampm = h24 < 12 ? "AM" : "PM";
  const h12 = h24 % 12 || 12;
  return `${h12}:${String(min).padStart(2, "0")} ${ampm} IST`;
}

function istPartsToUtc(hour: number, minute: number, ampm: "AM" | "PM"): string {
  const h24 = (hour % 12) + (ampm === "PM" ? 12 : 0);
  const total = ((h24 * 60 + minute - IST_OFFSET) % 1440 + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function ISTTimePicker({
  onAdd,
  disabled,
}: {
  onAdd: (utcTime: string) => void;
  disabled?: boolean;
}) {
  const [hour, setHour] = useState(9);
  const [minute, setMinute] = useState(0);
  const [ampm, setAmpm] = useState<"AM" | "PM">("AM");

  const sel =
    "bg-transparent text-slate-100 text-sm focus:outline-none cursor-pointer appearance-none text-center [&>option]:bg-slate-800";

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Picker control */}
      <div className="inline-flex items-center bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        {/* Hour */}
        <select
          value={hour}
          onChange={(e) => setHour(Number(e.target.value))}
          className={`${sel} pl-3 pr-1 py-2 w-12`}
        >
          {Array.from({ length: 12 }, (_, i) => i + 1).map((h) => (
            <option key={h} value={h}>
              {String(h).padStart(2, "0")}
            </option>
          ))}
        </select>

        <span className="text-slate-500 text-sm select-none">:</span>

        {/* Minute — 15-min increments matching Beat check interval */}
        <select
          value={minute}
          onChange={(e) => setMinute(Number(e.target.value))}
          className={`${sel} pl-1 pr-2 py-2 w-12`}
        >
          {[0, 15, 30, 45].map((m) => (
            <option key={m} value={m}>
              {String(m).padStart(2, "0")}
            </option>
          ))}
        </select>

        {/* AM / PM toggle */}
        <button
          type="button"
          onClick={() => setAmpm((a) => (a === "AM" ? "PM" : "AM"))}
          className="px-2.5 py-2 text-xs font-bold tracking-wide border-l border-slate-700 transition-colors
            text-violet-400 hover:text-violet-300 hover:bg-slate-700/60"
        >
          {ampm}
        </button>
      </div>

      <span className="text-xs text-slate-500 font-medium">IST</span>

      <button
        type="button"
        onClick={() => onAdd(istPartsToUtc(hour, minute, ampm))}
        disabled={disabled}
        className="px-3.5 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40
          text-white text-xs font-semibold rounded-lg transition-colors"
      >
        Add
      </button>
    </div>
  );
}
