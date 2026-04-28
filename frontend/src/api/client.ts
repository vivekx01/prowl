import axios from "axios";

const api = axios.create({ baseURL: "/api" });
export default api;

export interface Company {
  id: number;
  name: string;
  platform: string;
  active: boolean;
  config: Record<string, string>;
  created_at: string;
}

export interface Score {
  score: number;
  verdict: string;
  reason: string;
  processed_at: string;
}

export interface AppRecord {
  id: number;
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
