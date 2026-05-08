import { Navigate, Routes, Route } from "react-router-dom";
import { type ReactNode } from "react";
import Layout from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import JobsPage from "./pages/JobsPage";
import ApplicationsPage from "./pages/ApplicationsPage";
import InsightsPage from "./pages/InsightsPage";
import CompaniesPage from "./pages/CompaniesPage";
import ProfilePage from "./pages/ProfilePage";
import ScrapePage from "./pages/ScrapePage";
import CheckJDPage from "./pages/CheckJDPage";
import ScanPage from "./pages/ScanPage";
import CompanyListingsPage from "./pages/CompanyListingsPage";
import AdminPage from "./pages/AdminPage";
import AdminScoringPage from "./pages/AdminScoringPage";
import AdminAnalyticsPage from "./pages/AdminAnalyticsPage";

function RequireAuth({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAdmin } = useAuth();
  if (!isAdmin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  const { token } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={token ? <Navigate to="/" replace /> : <LoginPage />}
      />

      <Route
        path="/*"
        element={
          <RequireAuth>
            <Layout>
              <Routes>
                <Route path="/" element={<JobsPage />} />
                <Route path="/scan" element={<ScanPage />} />
                <Route path="/scan/:companyId" element={<CompanyListingsPage />} />
                <Route path="/applications" element={<ApplicationsPage />} />
                <Route path="/prowl-ai" element={<InsightsPage />} />
                <Route path="/check-jd" element={<CheckJDPage />} />
                <Route path="/profile" element={<ProfilePage />} />

                {/* Admin-only */}
                <Route path="/scrape" element={<RequireAdmin><ScrapePage /></RequireAdmin>} />
                <Route path="/companies" element={<RequireAdmin><CompaniesPage /></RequireAdmin>} />
                <Route path="/admin" element={<RequireAdmin><AdminPage /></RequireAdmin>} />
                <Route path="/admin/scoring/:userId" element={<RequireAdmin><AdminScoringPage /></RequireAdmin>} />
                <Route path="/admin/analytics" element={<RequireAdmin><AdminAnalyticsPage /></RequireAdmin>} />
              </Routes>
            </Layout>
          </RequireAuth>
        }
      />
    </Routes>
  );
}
