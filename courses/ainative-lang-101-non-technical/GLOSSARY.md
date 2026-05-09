# Glossary — Plain English

These entries describe the **AINL stack** in everyday words — how workflows become a **graph**, get **validated**, run under a **runtime**, call **adapters**, use **memory**, and optionally **patch** in saved wins.

**AINL / AI Native Lang** — A structured way to describe AI workflows so they can be checked, executed repeatedly, and connected to tools—instead of burying everything in one giant prompt.

**Adapter** — A controlled connection between the workflow engine and the outside world (for example: web APIs, databases, email, LLMs, memory). Think “certified plug” rather than “random script.”

**Audit trail** — A record of what the system did, in order. Useful for trust, debugging, and compliance conversations—without opening code.

**Branch** — A decision point: “if this, go here; otherwise go there.” Like a choose-your-own-adventure page, but for operations.

**Compile / compiler** — Turning a workflow description into an official internal plan the system can validate and run. Like translating a travel itinerary into boarding passes and gate numbers.

**Deterministic (in spirit)** — The workflow follows explicit steps. The world can still be messy (emails arrive late, APIs hiccup), but the *process map* is not improvised from scratch each time.

**Graph** — A map of steps and connections. Nodes are steps; edges are “what happens next” (including branches).

**Graph memory** — Memory organized so facts can relate to each other—more like a filing system with cross-links than one long scroll of chat history.

**GraphPatch / patching** — Saving a proven mini-workflow so the system can reuse it later—like adding a new page to the company playbook when someone discovers a better process.

**Guardrails** — Rules and checkpoints that prevent unsafe or off-brand actions—especially before money moves, emails send, or customer data leaves a boundary.

**IR (Intermediate Representation)** — The canonical internal shape of the workflow after compilation. You rarely need this word in non-technical meetings; say “the official workflow plan.”

**LLM** — The language model used for judgment-heavy steps (writing, summarizing, classifying). AINL helps ensure the model isn’t carrying the entire operating manual in every request.

**MCP (Model Context Protocol)** — A practical idea more than a jargon test: tools and resources can be exposed to agents in a standard way. Non-technical takeaway: “skills and tools can plug in cleanly.”

**Runtime** — The engine that actually walks through the workflow map and performs steps.

**Validation** — Checking the workflow for obvious problems *before* running it—like safety checks before takeoff.

**Workflow** — A repeatable sequence with decisions, tools, and outcomes—not just a one-off chat.
