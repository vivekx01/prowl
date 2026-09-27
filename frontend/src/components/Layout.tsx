import { NavLink, useNavigate } from "react-router-dom";
import { type ReactNode, type ComponentType, useState } from "react";
import {
  IconJobs, IconScrape, IconCompanies, IconInsights,
  IconApplications, IconCheckJD, IconScan, IconLogout, IconUsers, IconChart, IconKey,
} from "./Icons";
import { useAuth } from "../context/AuthContext";

const userNav = [
  { to: "/", label: "Recommendations", icon: IconJobs },
  { to: "/scan", label: "Find Openings", icon: IconScan },
  { to: "/applications", label: "Applications", icon: IconApplications },
  { to: "/prowl-ai", label: "Prowl AI", icon: IconInsights },
  { to: "/check-jd", label: "Check JD", icon: IconCheckJD },
  { to: "/api-access", label: "API Access", icon: IconKey },
  { to: "/profile", label: "Profile", icon: IconUsers },
];

const adminNav = [
  { to: "/scrape",            label: "Scrape",    icon: IconScrape },
  { to: "/companies",         label: "Companies", icon: IconCompanies },
  { to: "/admin",             label: "Users",     icon: IconUsers,  end: true },
  { to: "/admin/analytics",   label: "Analytics", icon: IconChart,  end: true },
];

function NavItem({
  to, label, icon: Icon, onClick, end,
}: {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  onClick?: () => void;
  end?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end ?? to === "/"}
      onClick={onClick}
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

function ProwlLogo({ size = "sm" }: { size?: "sm" | "xs" }) {
  const dim = size === "xs" ? "w-6 h-6" : "w-7 h-7";
  const svg = size === "xs" ? "w-3 h-3" : "w-4 h-4";
  return (
    <div className={`${dim} rounded-lg bg-violet-600 flex items-center justify-center shrink-0`}>
      <svg viewBox="0 0 48 48" className={svg} fill="none" xmlns="http://www.w3.org/2000/svg">
        <g stroke="white" strokeLinecap="round">
          <circle cx="10" cy="38" r="2.5" fill="white" stroke="none" />
          <path d="M 20,38 A 10,10 0 0 1 10,28" strokeWidth="3" />
          <path d="M 30,38 A 20,20 0 0 1 10,18" strokeWidth="3" />
          <path d="M 40,38 A 30,30 0 0 1 10,8" strokeWidth="3" />
        </g>
      </svg>
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  function closeSidebar() {
    setSidebarOpen(false);
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={closeSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={[
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-slate-800/60 bg-slate-950",
          "w-64 md:w-52",
          "transition-transform duration-200 ease-in-out",
          "md:relative md:z-auto md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
      >
        {/* Brand */}
        <div className="h-14 flex items-center px-5 border-b border-slate-800/60">
          <div className="flex items-center gap-2.5">
            <ProwlLogo />
            <span className="text-sm font-semibold text-slate-100 tracking-tight">Prowl</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {userNav.map((item) => (
            <NavItem key={item.to} {...item} onClick={closeSidebar} />
          ))}

          {isAdmin && (
            <>
              <div className="pt-3 pb-1">
                <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest px-3">
                  Admin
                </p>
              </div>
              {adminNav.map((item) => (
                <NavItem key={item.to} {...item} onClick={closeSidebar} />
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

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile header */}
        <header className="md:hidden h-14 flex items-center px-4 border-b border-slate-800/60 bg-slate-950 shrink-0">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            aria-label="Toggle menu"
            className="w-9 h-9 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
          >
            {sidebarOpen ? (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
          <div className="flex items-center gap-2 ml-3">
            <ProwlLogo size="xs" />
            <span className="text-sm font-semibold text-slate-100 tracking-tight">Prowl</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-4 md:p-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
