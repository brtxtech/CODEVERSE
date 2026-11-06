import { config } from "./config.ts";

export class HttpError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

const headers = {
  "Access-Control-Allow-Origin": config.allowedOrigin,
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Content-Type": "application/json",
};

export const preflight = () => new Response(null, { status: 204, headers });
export const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers });
export const fail = (e: unknown) => {
  if (e instanceof HttpError) return reply({ error: e.message }, e.status);
  console.error(e);                                   // details stay in the logs
  return reply({ error: "Internal error" }, 500);
};
