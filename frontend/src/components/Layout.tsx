import { NavLink, useNavigate } from "react-router-dom";
import { type ReactNode, type ComponentType } from "react";
import {
  IconJobs, IconScrape, IconCompanies, IconInsights,
  IconApplications, IconCheckJD, IconScan, IconLogout, IconUsers,
} from "./Icons";
import { useAuth } from "../context/AuthContext";

const userNav = [
  { to: "/", label: "Jobs", icon: IconJobs },
  { to: "/scan", label: "Find Openings", icon: IconScan },
  { to: "/applications", label: "Applications", icon: IconApplications },
  { to: "/prowl-ai", label: "Prowl AI", icon: IconInsights },
  { to: "/check-jd", label: "Check JD", icon: IconCheckJD },
  { to: "/profile", label: "Profile", icon: IconUsers },
];

const adminNav = [
  { to: "/scrape", label: "Scrape", icon: IconScrape },
  { to: "/companies", label: "Companies", icon: IconCompanies },
  { to: "/admin", label: "Users", icon: IconUsers },
];

function NavItem({ to, label, icon: Icon }: { to: string; label: string; icon: ComponentType<{ className?: string }> }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
          isActive
            ? "bg-violet-600/15 text-violet-300 border border-violet-500/20"
            : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 border border-transparent"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon className={`w-4 h-4 ${isActive ? "text-violet-400" : ""}`} />
          {label}
        </>
      )}
    </NavLink>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      {/* Sidebar */}
      <aside className="w-52 shrink-0 flex flex-col border-r border-slate-800/60 bg-slate-950">
        {/* Brand */}
        <div className="h-14 flex items-center px-5 border-b border-slate-800/60">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-violet-600 flex items-center justify-center shrink-0">
              <svg viewBox="0 0 48 48" className="w-4 h-4" fill="none" xmlns="http://www.w3.org/2000/svg">
                <g stroke="white" strokeLinecap="round">
                  <circle cx="10" cy="38" r="2.5" fill="white" stroke="none"/>
                  <path d="M 20,38 A 10,10 0 0 1 10,28" strokeWidth="3"/>
                  <path d="M 30,38 A 20,20 0 0 1 10,18" strokeWidth="3"/>
                  <path d="M 40,38 A 30,30 0 0 1 10,8"  strokeWidth="3"/>
                </g>
              </svg>
            </div>
            <span className="text-sm font-semibold text-slate-100 tracking-tight">Prowl</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {userNav.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}

          {isAdmin && (
            <>
              <div className="pt-3 pb-1">
                <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest px-3">
                  Admin
                </p>
              </div>
              {adminNav.map((item) => (
                <NavItem key={item.to} {...item} />
              ))}
            </>
          )}
        </nav>

        {/* User footer */}
        <div className="p-3 border-t border-slate-800/60">
          {user && (
            <div className="px-2 py-1.5 mb-1">
              <p className="text-xs font-medium text-slate-300 truncate">{user.name || user.email}</p>
              <p className="text-[10px] text-slate-600 truncate">{user.email}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm text-slate-500 hover:text-red-400 hover:bg-red-400/5 border border-transparent transition-all"
          >
            <IconLogout className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
