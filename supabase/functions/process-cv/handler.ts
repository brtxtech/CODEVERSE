// Request flow: validate -> authorize -> rate-limit -> read CV -> run pipeline -> save
import { createClient } from "npm:@supabase/supabase-js@2";
import { z } from "npm:zod@3";
import { config } from "./config.ts";
import { fail, HttpError, preflight, reply } from "./http.ts";
import { ClaudeCvExtractor } from "./claude-extractor.ts";
import type { CvExtractor } from "./cv.ts";
import { PipelineRepository } from "./repository.ts";

const Body = z.object({
  path: z.string().min(3).max(300).regex(/^[\w-]+\/[\w .()-]+\.(pdf|txt)$/i), // <uid>/<file>.pdf|txt
  top_jobs: z.number().int().min(1).max(10).default(5),
});

export async function handle(req: Request, extractor: CvExtractor = new ClaudeCvExtractor()): Promise<Response> {
  if (req.method === "OPTIONS") return preflight();
  try {
    if (req.method !== "POST") throw new HttpError(405, "POST only");
    const body = Body.safeParse(await req.json().catch(() => null));
    if (!body.success) throw new HttpError(400, "Invalid request");
    const { path, top_jobs } = body.data;

    const repo = new PipelineRepository(createClient(
      Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } },
    ));

    const uid = await repo.currentUserId();
    if (!path.startsWith(`${uid}/`)) throw new HttpError(403, "Not your file");
    if (await repo.runsInLastHour() >= config.maxRunsPerHour) throw new HttpError(429, "Too many CVs this hour");

    const file = await repo.download(path);
    if (file.size > config.maxFileBytes) throw new HttpError(413, "File too large (max 5 MB)");

    const cv = await extractor.extract(
      { bytes: new Uint8Array(await file.arrayBuffer()), isPdf: path.toLowerCase().endsWith(".pdf") },
      await repo.vocabulary(),
    );
    const result = await repo.run(cv, top_jobs);
    const cvId = await repo.save(path, cv, result);
    return reply({ cv_id: cvId, cv, ...result });
  } catch (e) {
    return fail(e);
  }
}
