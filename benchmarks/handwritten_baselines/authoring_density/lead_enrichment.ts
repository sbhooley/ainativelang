/**
 * Authoring-density baseline: B2B lead enrichment pipeline — idiomatic TypeScript.
 *
 * Semantically equivalent to examples/workflows/lead_enrichment.ainl.
 * Written in the style a proficient TypeScript developer (or LLM) would produce
 * when asked to "build a lead enrichment pipeline with caching and tier-based
 * sales context generation."
 *
 * Dependencies: node-fetch (or native fetch), openai  (npm install openai)
 */

import OpenAI from "openai";
import { readFileSync, writeFileSync, existsSync } from "fs";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AccountTier = "enterprise" | "mid_market" | "smb";

export interface EnrichmentData {
  name: string;
  employees: number;
  industry: string;
  country: string;
}

export interface LeadEnrichmentResult {
  tier: AccountTier;
  domain: string;
  name: string;
  industry: string;
  country: string;
  employees: number;
  salesContext: string;
  fromCache: boolean;
}

// ---------------------------------------------------------------------------
// File-backed cache (mirrors AINL cache adapter behaviour)
// ---------------------------------------------------------------------------

class FileCache {
  private readonly path: string;
  private data: Record<string, string>;

  constructor(path = ".lead_cache.json") {
    this.path = path;
    try {
      this.data = existsSync(path)
        ? (JSON.parse(readFileSync(path, "utf8")) as Record<string, string>)
        : {};
    } catch {
      this.data = {};
    }
  }

  get(key: string): string | undefined {
    return this.data[key];
  }

  set(key: string, value: string): void {
    this.data[key] = value;
    writeFileSync(this.path, JSON.stringify(this.data, null, 2));
  }
}

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export async function enrichLead(
  domain: string,
  enrichUrl: string,
  options?: {
    cache?: FileCache;
    openai?: OpenAI;
    httpTimeout?: number;
  }
): Promise<LeadEnrichmentResult> {
  const cache = options?.cache ?? new FileCache();
  const openai = options?.openai ?? new OpenAI();

  // Cache-first: skip enrichment API on repeat look-ups
  const cached = cache.get(domain);
  if (cached) {
    const [tier, , salesContext] = cached.split("|") as [AccountTier, string, string];
    return {
      tier,
      domain,
      name: "",
      industry: "",
      country: "",
      employees: 0,
      salesContext,
      fromCache: true,
    };
  }

  // Fetch firmographic data
  const response = await fetch(`${enrichUrl}${domain}`, {
    signal: AbortSignal.timeout((options?.httpTimeout ?? 15) * 1000),
  });
  if (!response.ok) {
    throw new Error(`Enrichment API error: ${response.status} ${response.statusText}`);
  }
  const data = (await response.json()) as EnrichmentData;

  const companyName = data.name ?? "";
  const industry = data.industry ?? "";
  const country = data.country ?? "";
  const empCount = Number(data.employees ?? 0);

  // Tier classification — deterministic, zero LLM tokens
  let tier: AccountTier;
  let prompt: string;
  let maxTokens: number;

  if (empCount > 500) {
    tier = "enterprise";
    prompt =
      `Write a 2-sentence enterprise sales context for ${companyName} ` +
      `in the ${industry} industry. ` +
      "Emphasise strategic value and multi-year ROI.";
    maxTokens = 150;
  } else if (empCount > 100) {
    tier = "mid_market";
    prompt =
      `Write a 2-sentence mid-market sales context for ${companyName} ` +
      `in the ${industry} industry. ` +
      "Focus on team adoption and productivity.";
    maxTokens = 120;
  } else {
    tier = "smb";
    prompt =
      `Write a 1-sentence SMB sales context for ${companyName} ` +
      `in the ${industry} industry. ` +
      "Keep it punchy and value-focused.";
    maxTokens = 80;
  }

  // Single LLM call for sales context
  const completion = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [{ role: "user", content: prompt }],
    max_tokens: maxTokens,
    temperature: 0.4,
  });
  const salesContext = completion.choices[0]?.message.content ?? "";

  // Cache result
  cache.set(domain, `${tier}|${domain}|${salesContext}`);

  return {
    tier,
    domain,
    name: companyName,
    industry,
    country,
    employees: empCount,
    salesContext,
    fromCache: false,
  };
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

if (process.argv[1] === __filename) {
  const domain = process.argv[2] ?? "stripe.com";
  const enrichUrl =
    process.argv[3] ??
    "https://company.clearbit.com/v2/companies/find?domain=";

  enrichLead(domain, enrichUrl)
    .then((r) => console.log(JSON.stringify(r, null, 2)))
    .catch((e) => {
      console.error(e);
      process.exit(1);
    });
}
