import type { SupabaseClient } from "npm:@supabase/supabase-js@2";
import { HttpError } from "./http.ts";
import type { ParsedCv } from "./cv.ts";

/** All data access in one place; every call runs as the signed-in user (RLS applies). */
export class PipelineRepository {
  constructor(private db: SupabaseClient) {}

  async currentUserId(): Promise<string> {
    const { data, error } = await this.db.auth.getUser();
    if (error || !data.user) throw new HttpError(401, "Not signed in");
    return data.user.id;
  }

  async runsInLastHour(): Promise<number> {
    const since = new Date(Date.now() - 3_600_000).toISOString();
    const { count, error } = await this.db.from("cvs").select("id", { count: "exact", head: true }).gte("created_at", since);
    if (error) throw error;
    return count ?? 0;
  }

  async download(path: string): Promise<Blob> {
    const { data, error } = await this.db.storage.from("cvs").download(path);
    if (error || !data) throw new HttpError(404, "File not found");
    return data;
  }

  async vocabulary(): Promise<string[]> {
    const { data, error } = await this.db.from("skill_vocabulary").select("skill");
    if (error) throw error;
    return (data ?? []).map((r: { skill: string }) => r.skill);
  }

  async run(cv: ParsedCv, topJobs: number) {
    const { data, error } = await this.db.rpc("run_pipeline", { p_cv: cv, p_top_jobs: topJobs });
    if (error) throw error;
    return data;
  }

  async save(path: string, parsed: ParsedCv, result: unknown): Promise<string> {
    const { data, error } = await this.db.from("cvs").insert({ storage_path: path, parsed, result }).select("id").single();
    if (error) throw error;
    return data.id;
  }
}
