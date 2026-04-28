import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import JobsPage from "./pages/JobsPage";
import ApplicationsPage from "./pages/ApplicationsPage";
import InsightsPage from "./pages/InsightsPage";
import CompaniesPage from "./pages/CompaniesPage";
import ProfilePage from "./pages/ProfilePage";
import ScrapePage from "./pages/ScrapePage";
import CheckJDPage from "./pages/CheckJDPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<JobsPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/prowl-ai" element={<InsightsPage />} />
        <Route path="/scrape" element={<ScrapePage />} />
        <Route path="/companies" element={<CompaniesPage />} />
        <Route path="/check-jd" element={<CheckJDPage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Routes>
    </Layout>
  );
}
