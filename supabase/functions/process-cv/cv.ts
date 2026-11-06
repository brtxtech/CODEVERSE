import { z } from "npm:zod@3";

const term = z.string().trim().min(1).max(60).transform((s) => s.toLowerCase());

/** Validated shape of what the LLM returns. Everything downstream can trust it. */
export const ParsedCv = z.object({
  contact: z.object({
    name: z.string().max(120).nullable().default(null),
    location: z.object({
      city: z.string().max(80).nullable().default(null),
      country: z.string().max(80).nullable().default(null),
    }).default({ city: null, country: null }),
  }).default({ name: null, location: { city: null, country: null } }),
  skills: z.array(term).max(100).default([]),
  interests: z.array(term).max(30).default([]),
});
export type ParsedCv = z.infer<typeof ParsedCv>;

/** Port: any CV reader (Claude today, something else tomorrow) implements this. */
export interface CvExtractor {
  extract(file: { bytes: Uint8Array; isPdf: boolean }, vocabulary: string[]): Promise<ParsedCv>;
}
