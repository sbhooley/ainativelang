/**
 * Authoring-density baseline: multi-source order processing pipeline.
 * LLM-GENERATED STYLE — verbose, defensive, fully annotated.
 *
 * Semantically equivalent to examples/workflows/data_pipeline.ainl.
 *
 * This file models what a capable LLM (GPT-4o / Claude Sonnet) produces when
 * asked to implement the same pipeline from scratch in TypeScript — complete with:
 *   - Full type annotations and JSDoc comments
 *   - Structured error types
 *   - Retry wrappers for external calls
 *   - Zod-style runtime validation
 *   - File-backed cache with error handling
 *   - Append-only memory/audit log
 *   - Per-function error handling with Result types
 *   - Argparse-style CLI entry point
 *
 * Dependencies: openai, zod  (npm install openai zod)
 */

import OpenAI from "openai";
import { readFileSync, writeFileSync, existsSync, appendFileSync } from "fs";

// ---------------------------------------------------------------------------
// Enumerations
// ---------------------------------------------------------------------------

export type FulfilmentType = "digital" | "physical" | "subscription";

export type OrderStatus =
  | "processing:digital"
  | "processing:physical"
  | "processing:subscription"
  | "processing:vip"
  | "processing:enterprise_vip"
  | "backorder:physical"
  | "rejected:fraud"
  | "rejected:invalid"
  | "duplicate";

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface CustomerData {
  customerId: string;
  tier: string;
  fraudScore: number;
  discountPct: number;
  subscriptionId?: string;
}

export interface ProductData {
  productId: string;
  name: string;
  inventory: number;
  category: string;
}

export interface OrderInput {
  orderId: string;
  customerId: string;
  productId: string;
  orderValue: number;
  fulfilmentType: FulfilmentType;
  customerApi: string;
  productApi: string;
}

export interface OrderResult {
  orderId: string;
  status: OrderStatus;
  dispatchRecord: string;
  confirmationEmail?: string;
  fromCache: boolean;
  processingTimeMs: number;
  error?: string;
}

// ---------------------------------------------------------------------------
// File-backed cache (mirrors AINL cache adapter)
// ---------------------------------------------------------------------------

class FileCache {
  private readonly path: string;
  private data: Record<string, string>;

  constructor(path = ".order_cache.json") {
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
    try {
      writeFileSync(this.path, JSON.stringify(this.data, null, 2));
    } catch (err) {
      console.error(`Cache write failed for '${key}':`, err);
    }
  }
}

// ---------------------------------------------------------------------------
// Append-only memory log (mirrors AINL memory adapter APPEND)
// ---------------------------------------------------------------------------

class MemoryLog {
  private readonly path: string;

  constructor(path = ".order_memory.jsonl") {
    this.path = path;
  }

  append(namespace: string, tag: string, orderId: string, payload: string): void {
    const entry = JSON.stringify({ namespace, tag, orderId, payload, ts: Date.now() });
    try {
      appendFileSync(this.path, entry + "\n");
    } catch (err) {
      console.error("Memory log append failed:", err);
    }
  }
}

// ---------------------------------------------------------------------------
// HTTP helpers with retry
// ---------------------------------------------------------------------------

async function fetchWithRetry<T>(
  url: string,
  timeout = 10_000,
  retries = 3
): Promise<T> {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(timeout) });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return (await response.json()) as T;
    } catch (err) {
      lastError = err as Error;
      if (attempt < retries - 1) {
        await new Promise((r) => setTimeout(r, Math.pow(2, attempt) * 1000));
      }
    }
  }
  throw lastError ?? new Error("Request failed after retries");
}

async function fetchCustomer(apiBase: string, customerId: string): Promise<CustomerData> {
  const data = await fetchWithRetry<Record<string, unknown>>(`${apiBase}${customerId}`);
  return {
    customerId,
    tier: String(data.tier ?? "standard"),
    fraudScore: Number(data.fraud_score ?? 0),
    discountPct: Number(data.discount_pct ?? 0),
    subscriptionId: data.subscription_id ? String(data.subscription_id) : undefined,
  };
}

async function fetchProduct(apiBase: string, productId: string): Promise<ProductData> {
  const data = await fetchWithRetry<Record<string, unknown>>(`${apiBase}${productId}`);
  return {
    productId,
    name: String(data.name ?? ""),
    inventory: Number(data.inventory ?? 0),
    category: String(data.category ?? ""),
  };
}

// ---------------------------------------------------------------------------
// LLM helpers with retry
// ---------------------------------------------------------------------------

async function llmComplete(
  prompt: string,
  maxTokens: number,
  temperature: number,
  openai: OpenAI,
  retries = 3
): Promise<string> {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const completion = await openai.chat.completions.create({
        model: "gpt-4o",
        messages: [{ role: "user", content: prompt }],
        max_tokens: maxTokens,
        temperature,
      });
      return completion.choices[0]?.message.content ?? "";
    } catch (err) {
      lastError = err as Error;
      if (attempt < retries - 1) {
        await new Promise((r) => setTimeout(r, Math.pow(2, attempt) * 1000));
      }
    }
  }
  throw lastError ?? new Error("LLM completion failed after retries");
}

async function generateEnterpriseConfirmation(
  customerId: string,
  productName: string,
  openai: OpenAI
): Promise<string> {
  return llmComplete(
    `Generate a professional enterprise order confirmation for ${customerId} ` +
      `ordering ${productName}. ` +
      "Mention dedicated account manager, priority SLA, and invoice terms.",
    250,
    0.4,
    openai
  );
}

async function generateVipConfirmation(
  customerId: string,
  productName: string,
  openai: OpenAI
): Promise<string> {
  return llmComplete(
    `Generate a warm VIP order confirmation for ${customerId} ` +
      `ordering ${productName}. ` +
      "Mention priority handling, estimated delivery, and loyalty points.",
    200,
    0.4,
    openai
  );
}

// ---------------------------------------------------------------------------
// Routing helpers (deterministic — zero LLM tokens)
// ---------------------------------------------------------------------------

const VIP_THRESHOLD = 500.0;
const VIP_SUBSCRIPTION_THRESHOLD = 200.0;

function isVip(orderValue: number, fulfilmentType: FulfilmentType): boolean {
  if (fulfilmentType === "digital" && orderValue > VIP_THRESHOLD) return true;
  if (fulfilmentType === "physical" && orderValue > VIP_THRESHOLD) return true;
  if (fulfilmentType === "subscription" && orderValue > VIP_SUBSCRIPTION_THRESHOLD) return true;
  return false;
}

// ---------------------------------------------------------------------------
// Main pipeline
// ---------------------------------------------------------------------------

export async function processOrder(
  orderId: string,
  customerId: string,
  productId: string,
  orderValue: number,
  fulfilmentType: FulfilmentType,
  customerApi: string,
  productApi: string,
  options?: {
    cache?: FileCache;
    memory?: MemoryLog;
    openai?: OpenAI;
  }
): Promise<OrderResult> {
  const t0 = Date.now();
  const cache = options?.cache ?? new FileCache();
  const memory = options?.memory ?? new MemoryLog();
  const openai = options?.openai ?? new OpenAI();

  const stateKey = `order_state:${orderId}`;

  // Step 1: deduplication check
  const cachedState = cache.get(stateKey);
  if (cachedState) {
    return {
      orderId,
      status: "duplicate",
      dispatchRecord: `duplicate:${orderId}`,
      fromCache: true,
      processingTimeMs: Date.now() - t0,
    };
  }

  // Step 2: input validation
  if (orderValue <= 0) {
    cache.set(stateKey, "rejected:invalid");
    return {
      orderId,
      status: "rejected:invalid",
      dispatchRecord: "rejected:invalid_order_value",
      fromCache: false,
      processingTimeMs: Date.now() - t0,
    };
  }

  const validFulfilment: FulfilmentType[] = ["digital", "physical", "subscription"];
  if (!validFulfilment.includes(fulfilmentType)) {
    cache.set(stateKey, "rejected:invalid");
    return {
      orderId,
      status: "rejected:invalid",
      dispatchRecord: `rejected:unknown_fulfilment_type:${fulfilmentType}`,
      fromCache: false,
      processingTimeMs: Date.now() - t0,
    };
  }

  // Step 3: customer enrichment
  let customer: CustomerData;
  try {
    customer = await fetchCustomer(customerApi, customerId);
  } catch (err) {
    return {
      orderId,
      status: "rejected:invalid",
      dispatchRecord: "rejected:customer_enrichment_error",
      fromCache: false,
      processingTimeMs: Date.now() - t0,
      error: String(err),
    };
  }

  // Step 4: fraud gate
  if (customer.fraudScore > 75) {
    cache.set(stateKey, "rejected:fraud");
    return {
      orderId,
      status: "rejected:fraud",
      dispatchRecord: `blocked:fraud_score=${customer.fraudScore}`,
      fromCache: false,
      processingTimeMs: Date.now() - t0,
    };
  }

  // Step 5: product enrichment
  let product: ProductData;
  try {
    product = await fetchProduct(productApi, productId);
  } catch (err) {
    return {
      orderId,
      status: "rejected:invalid",
      dispatchRecord: "rejected:product_enrichment_error",
      fromCache: false,
      processingTimeMs: Date.now() - t0,
      error: String(err),
    };
  }

  // Steps 6–8: routing + optional LLM email
  if (isVip(orderValue, fulfilmentType)) {
    let email: string;
    let status: OrderStatus;

    if (customer.tier === "enterprise") {
      email = await generateEnterpriseConfirmation(customerId, product.name, openai);
      status = "processing:enterprise_vip";
    } else {
      email = await generateVipConfirmation(customerId, product.name, openai);
      status = "processing:vip";
    }

    cache.set(stateKey, status);
    memory.append("orders", status.includes("enterprise") ? "vip_enterprise" : "vip", orderId, email);

    return {
      orderId,
      status,
      dispatchRecord: `dispatch:vip:${fulfilmentType}:${productId}`,
      confirmationEmail: email,
      fromCache: false,
      processingTimeMs: Date.now() - t0,
    };
  }

  if (fulfilmentType === "digital") {
    cache.set(stateKey, "processing:digital");
    return {
      orderId,
      status: "processing:digital",
      dispatchRecord: `dispatch:digital:immediate:${productId}`,
      fromCache: false,
      processingTimeMs: Date.now() - t0,
    };
  }

  if (fulfilmentType === "physical") {
    if (product.inventory > 0) {
      cache.set(stateKey, "processing:physical");
      return {
        orderId,
        status: "processing:physical",
        dispatchRecord: `dispatch:physical:warehouse:${productId}`,
        fromCache: false,
        processingTimeMs: Date.now() - t0,
      };
    } else {
      cache.set(stateKey, "backorder:physical");
      return {
        orderId,
        status: "backorder:physical",
        dispatchRecord: `backorder:physical:notify:${customerId}`,
        fromCache: false,
        processingTimeMs: Date.now() - t0,
      };
    }
  }

  // Subscription
  const subId = customer.subscriptionId ?? customerId;
  cache.set(stateKey, "processing:subscription");
  return {
    orderId,
    status: "processing:subscription",
    dispatchRecord: `dispatch:subscription:renew:${subId}`,
    fromCache: false,
    processingTimeMs: Date.now() - t0,
  };
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

if (process.argv[1] === new URL(import.meta.url).pathname) {
  processOrder(
    process.argv[2] ?? "ORD-2026-0001",
    process.argv[3] ?? "CUST-42",
    process.argv[4] ?? "PROD-SKU-001",
    Number(process.argv[5] ?? 750),
    (process.argv[6] as FulfilmentType) ?? "digital",
    process.argv[7] ?? "https://api.example.com/customers/",
    process.argv[8] ?? "https://api.example.com/products/"
  )
    .then((r) => console.log(JSON.stringify(r, null, 2)))
    .catch((e) => { console.error(e); process.exit(1); });
}
