// Edge Function: process-cv
// Deploy: supabase functions deploy process-cv
// Secret: supabase secrets set ANTHROPIC_API_KEY=...   (optional: ALLOWED_ORIGIN, MAX_CV_RUNS_PER_HOUR)
// Call:   supabase.functions.invoke('process-cv', { body: { path: '<uid>/cv.pdf', top_jobs: 5 } })
import { handle } from "./handler.ts";

Deno.serve((req) => handle(req));
