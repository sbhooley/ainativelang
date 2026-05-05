/**
 * Authoring-density baseline: enterprise health monitor — idiomatic TypeScript.
 *
 * Semantically equivalent to examples/benchmark/enterprise_monitor.ainl.
 * Written in the style a proficient TypeScript developer (or LLM) would produce
 * when asked to "build a health monitor that polls an HTTP endpoint, routes
 * by severity, generates LLM incident alerts only when needed, and caches state."
 *
 * Dependencies: openai  (npm install openai)
 */

import OpenAI from "openai";
import { readFileSync, writeFileSync, existsSync } from "fs";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Severity = "healthy" | "degraded" | "critical";

export interface MonitorResult {
  severity: Severity;
  endpointUrl: string;
  statusCode: number | null;
  latencyMs: number;
  alertText: string | null;
}

// ---------------------------------------------------------------------------
// File-backed cache (mirrors AINL cache adapter behaviour)
// ---------------------------------------------------------------------------

class FileCache {
  private readonly path: string;
  private data: Record<string, string>;

  constructor(path = ".monitor_cache.json") {
    this.path = path;
    try {
      this.data = existsSync(path)
        ? (JSON.parse(readFileSync(path, "utf8")) as Record<string, string>)
        : {};
    } catch {
      this.data = {};
    }
  }

  set(key: string, value: string): void {
    this.data[key] = value;
    writeFileSync(this.path, JSON.stringify(this.data, null, 2));
  }
}

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export async function checkEndpoint(
  endpointUrl: string,
  thresholdMs: number,
  options?: {
    cache?: FileCache;
    openai?: OpenAI;
    httpTimeoutMs?: number;
  }
): Promise<MonitorResult> {
  const cache = options?.cache ?? new FileCache();
  const openai = options?.openai ?? new OpenAI();
  const timeoutMs = options?.httpTimeoutMs ?? 10_000;

  // Poll the health endpoint
  const t0 = Date.now();
  let statusCode: number | null = null;
  let isUp = false;

  try {
    const response = await fetch(endpointUrl, {
      signal: AbortSignal.timeout(timeoutMs),
    });
    statusCode = response.status;
    isUp = statusCode === 200;
  } catch {
    // Network error / timeout — treat as down
  }
  const latencyMs = Date.now() - t0;

  // Severity routing — zero LLM tokens
  let severity: Severity;
  if (!isUp) {
    severity = "critical";
  } else if (latencyMs > thresholdMs) {
    severity = "degraded";
  } else {
    severity = "healthy";
  }

  // LLM alert generation — only for non-healthy states
  let alertText: string | null = null;

  if (severity === "critical") {
    const prompt =
      `Critical: endpoint ${endpointUrl} is DOWN. ` +
      `HTTP status: ${statusCode ?? "N/A"}. ` +
      "Draft a concise ops incident alert.";
    const completion = await openai.chat.completions.create({
      model: "gpt-4o",
      messages: [{ role: "user", content: prompt }],
      max_tokens: 200,
      temperature: 0.2,
    });
    alertText = completion.choices[0]?.message.content ?? null;
  } else if (severity === "degraded") {
    const prompt =
      `Degraded: endpoint ${endpointUrl} latency ${latencyMs}ms ` +
      `exceeds threshold ${thresholdMs}ms. ` +
      "Draft a concise ops alert.";
    const completion = await openai.chat.completions.create({
      model: "gpt-4o",
      messages: [{ role: "user", content: prompt }],
      max_tokens: 150,
      temperature: 0.3,
    });
    alertText = completion.choices[0]?.message.content ?? null;
  }

  // Cache severity state
  cache.set("monitor_last_severity", severity);
  if (alertText !== null) {
    cache.set("monitor_last_alert", alertText);
  }

  return { severity, endpointUrl, statusCode, latencyMs, alertText };
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

if (process.argv[1] === new URL(import.meta.url).pathname) {
  const endpointUrl = process.argv[2] ?? "https://httpbin.org/status/200";
  const thresholdMs = Number(process.argv[3] ?? 500);

  checkEndpoint(endpointUrl, thresholdMs)
    .then((r) => console.log(JSON.stringify(r, null, 2)))
    .catch((e) => {
      console.error(e);
      process.exit(1);
    });
}
