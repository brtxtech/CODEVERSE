export const config = {
  anthropicKey: Deno.env.get("ANTHROPIC_API_KEY") ?? "",
  model: Deno.env.get("ANTHROPIC_MODEL") ?? "claude-sonnet-5-5",
  maxFileBytes: 5 * 1024 * 1024,
  maxRunsPerHour: Number(Deno.env.get("MAX_CV_RUNS_PER_HOUR") ?? 10),
  aiTimeoutMs: 45_000,
  allowedOrigin: Deno.env.get("ALLOWED_ORIGIN") ?? "*", // set to your site in production
} as const;
