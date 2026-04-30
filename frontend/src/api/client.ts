import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// Attach stored token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("prowl_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirect to login on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("prowl_token");
      localStorage.removeItem("prowl_user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;

export interface User {
  user_id: number;
  email: string;
  name: string;
  is_admin: boolean;
}

export interface Company {
  id: number;
  name: string;
  platform: string;
  active: boolean;
  config: Record<string, string>;
  created_at: string;
  listing_count: number;
}

export interface JobListing {
  id: number;
  company_id: number;
  company_name: string;
  title: string;
  location: string;
  posted_on: string;
  posted_date: string | null;
  url: string;
  department: string;
  first_seen_at: string;
}

export interface Score {
  score: number;
  verdict: string;
  reason: string;
  processed_at: string;
}

export interface AppRecord {
  id: number;
  listing_id: number;
  status: string;
  applied_at: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: number;
  company_id: number;
  company_name: string;
  job_req_id: string;
  title: string;
  location: string;
  posted_on: string;
  posted_date: string | null;
  url: string;
  department: string;
  platform: string;
  first_seen_at: string;
  score: Score | null;
  application: AppRecord | null;
}

export interface RunLog {
  id: number;
  timestamp: string;
  level: string;
  message: string;
}

export interface ScrapeRun {
  id: number;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  company_ids: number[] | null;
  completed_company_ids: number[];
  companies_total: number;
  companies_done: number;
  new_listings: number;
  apply_count: number;
  input_tokens: number;
  output_tokens: number;
  celery_task_id: string | null;
}

export interface ScoreRun {
  id: number;
  user_id: number;
  celery_task_id: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  companies_total: number;
  companies_done: number;
  apply_count: number;
  input_tokens: number;
  output_tokens: number;
  current_company_id: number | null;
  company_results: CompanyResult[];
}

export interface CompanyResult {
  id: number;
  name: string;
  platform: string;
  matches: number;
}

export interface AdminScoreRun {
  id: number;
  user_id: number;
  user_email: string | null;
  status: string;
  days_back: number | null;
  started_at: string | null;
  finished_at: string | null;
  companies_total: number;
  companies_done: number;
  apply_count: number;
  input_tokens: number;
  output_tokens: number;
}
