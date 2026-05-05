import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";
import { useAuth } from "../context/AuthContext";


export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email: form.email, password: form.password });
      login(data.access_token, {
        user_id: data.user_id,
        email: data.email,
        name: data.name,
        is_admin: data.is_admin,
      });
      navigate("/");
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-9 h-9 rounded-xl bg-violet-600 flex items-center justify-center">
            <svg viewBox="0 0 48 48" className="w-5 h-5" fill="none" xmlns="http://www.w3.org/2000/svg">
              <g stroke="white" strokeLinecap="round">
                <circle cx="10" cy="38" r="2.5" fill="white" stroke="none"/>
                <path d="M 20,38 A 10,10 0 0 1 10,28" strokeWidth="3"/>
                <path d="M 30,38 A 20,20 0 0 1 10,18" strokeWidth="3"/>
                <path d="M 40,38 A 30,30 0 0 1 10,8"  strokeWidth="3"/>
              </g>
            </svg>
          </div>
          <span className="text-xl font-semibold text-slate-100 tracking-tight">Prowl</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8">
          <h1 className="text-lg font-semibold text-slate-100 mb-1">Sign in</h1>
          <p className="text-sm text-slate-500 mb-6">Welcome back</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="you@example.com"
                required
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30 transition"
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
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/30 transition"
              />
            </div>

            {error && (
              <p className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-medium rounded-lg py-2.5 text-sm transition"
            >
              {loading ? "Please wait…" : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
