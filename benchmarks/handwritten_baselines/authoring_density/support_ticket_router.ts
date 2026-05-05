/**
 * Authoring-density baseline: customer support ticket router — idiomatic TypeScript.
 *
 * Semantically equivalent to examples/workflows/support_ticket_router.ainl.
 * Written in the style a proficient TypeScript developer (or LLM) would produce
 * when asked to "build a support ticket triage pipeline that classifies priority
 * and category, routes to the correct team, and generates a draft first response."
 *
 * Dependencies: openai  (npm install openai)
 */

import OpenAI from "openai";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Priority = "critical" | "high" | "normal" | "low";
export type Category = "bug" | "billing" | "feature" | "general";

export interface TicketRouteResult {
  ticketId: string;
  priority: Priority;
  category: Category;
  team: string;
  slaHours: number;
  draftResponse: string;
}

// ---------------------------------------------------------------------------
// Routing table (deterministic — zero LLM tokens)
// ---------------------------------------------------------------------------

type RouteKey = `${Priority}|${Category}`;

const TEAM_TABLE: Partial<Record<RouteKey, { team: string; slaHours: number }>> = {
  "critical|billing":  { team: "billing-escalations",  slaHours: 2 },
  "critical|bug":      { team: "engineering-oncall",    slaHours: 1 },
  "critical|feature":  { team: "engineering-oncall",    slaHours: 1 },
  "critical|general":  { team: "engineering-oncall",    slaHours: 1 },
  "high|billing":      { team: "billing",               slaHours: 4 },
  "high|bug":          { team: "support-tier2",         slaHours: 8 },
  "high|feature":      { team: "support-tier2",         slaHours: 8 },
  "high|general":      { team: "support-tier2",         slaHours: 8 },
};

const DRAFT_INSTRUCTIONS: Partial<Record<RouteKey, string>> = {
  "critical|billing":
    "Write an empathetic urgent response for this critical billing issue. " +
    "State a 2-hour SLA and offer a direct callback.",
  "critical|bug":
    "Write an empathetic urgent acknowledgment for this critical engineering issue. " +
    "State the on-call team is engaged and commit to a 1-hour response.",
  "critical|feature":
    "Write an empathetic urgent acknowledgment for this critical issue. " +
    "State the on-call team is engaged and commit to a 1-hour response.",
  "critical|general":
    "Write an empathetic urgent acknowledgment for this critical issue. " +
    "State the on-call team is engaged and commit to a 1-hour response.",
  "high|billing":
    "Write a professional response for this high-priority billing enquiry. " +
    "Confirm 4-hour SLA and name the billing team as the owner.",
  "high|bug":
    "Write a professional response for this high-priority support ticket. " +
    "Confirm tier-2 assignment and 8-hour SLA.",
  "high|feature":
    "Write a professional response for this high-priority ticket. " +
    "Confirm tier-2 assignment and 8-hour SLA.",
  "high|general":
    "Write a professional response for this high-priority ticket. " +
    "Confirm tier-2 assignment and 8-hour SLA.",
};

const NORMAL_DRAFT =
  "Write a friendly, helpful first response for this support ticket. Confirm 24-hour SLA.";

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export async function routeTicket(
  ticketId: string,
  ticketText: string,
  openai?: OpenAI
): Promise<TicketRouteResult> {
  const client = openai ?? new OpenAI();

  const classify = async (instruction: string): Promise<string> => {
    const completion = await client.chat.completions.create({
      model: "gpt-4o",
      messages: [
        { role: "user", content: `${instruction} Ticket: ${ticketText}` },
      ],
      max_tokens: 10,
      temperature: 0,
    });
    return (completion.choices[0]?.message.content ?? "").trim().toLowerCase();
  };

  // LLM call 1: classify priority
  const priorityRaw = await classify(
    "Classify this support ticket priority as exactly one word — " +
    "critical, high, normal, or low."
  );
  const priority: Priority = (["critical", "high", "normal", "low"] as Priority[]).includes(
    priorityRaw as Priority
  )
    ? (priorityRaw as Priority)
    : "normal";

  // LLM call 2: classify category
  const categoryRaw = await classify(
    "Classify this support ticket category as exactly one word — " +
    "bug, billing, feature, or general."
  );
  const category: Category = (["bug", "billing", "feature", "general"] as Category[]).includes(
    categoryRaw as Category
  )
    ? (categoryRaw as Category)
    : "general";

  // Deterministic routing — zero LLM tokens
  const routeKey: RouteKey = `${priority}|${category}`;
  const route = TEAM_TABLE[routeKey];
  const team = route?.team ?? "support-tier1";
  const slaHours = route?.slaHours ?? 24;
  const draftInstruction = DRAFT_INSTRUCTIONS[routeKey] ?? NORMAL_DRAFT;

  // LLM call 3: generate draft response
  const draftCompletion = await client.chat.completions.create({
    model: "gpt-4o",
    messages: [
      { role: "user", content: `${draftInstruction} Ticket: ${ticketText}` },
    ],
    max_tokens: 200,
    temperature: 0.5,
  });
  const draftResponse = draftCompletion.choices[0]?.message.content ?? "";

  return { ticketId, priority, category, team, slaHours, draftResponse };
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

if (process.argv[1] === new URL(import.meta.url).pathname) {
  const ticketId = process.argv[2] ?? "TKT-0001";
  const ticketText =
    process.argv[3] ??
    "I was charged twice for my subscription this month and need an immediate refund.";

  routeTicket(ticketId, ticketText)
    .then((r) => console.log(JSON.stringify(r, null, 2)))
    .catch((e) => {
      console.error(e);
      process.exit(1);
    });
}
