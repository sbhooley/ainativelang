# Sunrise Ceramics — five mini episodes

**How to read this page:** Each episode begins with **why it exists**—that sentence tells you which AINL idea the scene is about. After that, read straight through; you should not need to jump around. **Bold** highlights one main teaching phrase per beat, **names**, or **words you’d actually see on a screen**. Everything else stays normal text so the highlights do not turn into noise.

**Who’s who:** **Jordan** runs day-to-day ops. **Ms. Rivera** is a regular customer. **Dev** handles shipping systems. **Sam** handles finance.

**Story shape (read this once):** These are **five spotlight scenes**, not five chapters of one thriller. Same shop and cast, **different moments in time**—packing, customs season, a coupon scare, a finance question, a carrier outage. If you read them hunting for one linear plot, they will feel jumpy; they’re meant to feel like **five magazine columns**, each illustrating **one** habit. The table below is your map.

| # | Topic | Plain takeaway |
|---|--------|----------------|
| 1 | Memory in the workflow | The system reminds staff **at the step where it matters**. |
| 2 | Saving a winning path (GraphPatch) | After chaos, the fix becomes **the usual way you ship**. |
| 3 | Human gate before risk | A scary action **waits for a person** before it runs. |
| 4 | Audit trail | You get **a dated list in order**, not a guessing game. |
| 5 | When a tool fails | **Try again, then fall back, then alert someone**—already decided in advance. |

**Skim — each episode → corner of AINL** (the detailed explanation lives under **The AINL point** in each scene):

1. **Memory** attached to the **workflow graph**, surfaced by the **runtime** at the step where it matters—not chat-only recall.  
2. **GraphPatch** — promote a surviving procedure into the **official map** (**graph** / compiled **IR**).  
3. **Human gate** — a **branch** in the graph that **blocks** risky work until a person approves.  
4. **Audit trail** — **ordered execution** and decisions you can **replay** (trust, compliance, debugging).  
5. **Adapters** + **failure handling** — **retries and fallbacks** as explicit **branches** when external tools misbehave.

The big picture frame from **[CHEAT-SHEET.md](./CHEAT-SHEET.md)** still applies: **write/govern** the map → **compile/check** it → **run** it with **adapters**, **memory**, and **branches**.

---

### Episode 1 — The glaze that isn’t “just preference”

*Starts here—a repeat customer’s quiet detail has to survive until packing day.*

**Why you’re reading this:** Important customer facts belong **in the workflow**, so they surface **at the moment they matter**—not lost in old chat when the shop is rushing.

Ms. Rivera comes in for mugs she’ll ship to her sister, like she always does. At the counter she lowers her voice—almost apologetic—and says the cobalt-blue glaze dust isn’t dramatic on the news, but near tissue paper it’s a real problem for her family. **Jordan** nods, writes nothing frantic on a sticky note, and instead asks one boring question: “Should we flag your account so packing never reaches for the blue tissue?” Rivera looks relieved that someone treated it like logistics, not drama.

Sunrise doesn’t leave that sentence in a chat thread that scrolls away. They attach it to Rivera’s customer record and to **packing**: what can touch the box, what cannot. Months later she checks out online while Jordan is elbow-deep in orders on a Saturday. Jordan isn’t squinting at old messages trying to remember a face. The tablet beside the tape gun already says what this box needs—**sage green tissue**, Rivera’s sensitivity flagged—before the first sheet slides in.

**The AINL point — what this scene is really about**

*In human terms:* Sunrise is doing the opposite of “I think we talked about that in email once.” The fact about Rivera is **carried by the process**—it shows up on the **packing** step, not as a wall of text the model has to rediscover every time. That is what people mean by **memory that actually helps on the busy day**.

*Where this sits in AINL:* This is **workflow memory** tied to your **graph** (your official map of steps). It’s related to **memory** and **state** in the system—not “whatever the chat remembers,” but facts bound to **nodes** (customer → pack → ship) so the **runtime** can inject them **at the right step**. You’ll see the same idea in docs as **memory**, **graph**, and **runtime** working together.

*Why it matters:* If fragile details live only in prompts or old threads, every rush hour becomes a recall test. Wiring memory into the map is how you get **repeatable care** without burning money and attention re-explaining the same rule.

---

### Episode 2 — The week customs went chaotic

*Different season, same shop—international orders were eating Sunrise alive until one sequence kept working.*

**Why you’re reading this:** When a team finally finds a sequence that works under fire, the useful habit is to **make that sequence the default next time** instead of reinventing it every meltdown. Technical docs call that promotion **GraphPatch**; here it means **save the win into how you always operate**.

For ten days the export inbox sounds like a machine gun: wrong HS codes, sudden photo demands, customers who only wanted a birthday mug and now think their parcel vanished at the border. Everyone invents a new fix each morning—until one Thursday **Dev** notices something strange. The orders that actually clear all share the same awkward rhythm: double-check the code, snap how it’s packed so nobody can argue, send the apology people actually stop yelling at, watch tracking for five days, and only then scream for help if it’s still stuck.

When the storm finally thins, **Jordan** finds **Dev** at the kitchenette microwave, still wearing the face of someone who hasn’t slept. “We can’t call that week luck,” Jordan says. “We need it written down like a recipe.” They name the route something deliberately dull—**Fragile Export — v2**—so nobody has to reverse-engineer courage the next time a border decides to be weird.

**The AINL point — what this scene is really about**

*In human terms:* After a crisis, the worst outcome is “we survived by heroics, then forgot.” **Fragile Export — v2** is **the playbook**: the sequence that already survived reality becomes what new orders ride on. Nobody has to improvise the whole dance from memory next time.

*Where this sits in AINL:* This is **GraphPatch** in technical language—**patching the graph** so a proven path becomes part of the **official workflow map** (the **graph / IR** people compile and run). It connects **write/govern** (what you learned) with **run** (what actually executes tomorrow). Think: **save the winning procedure into the map**, not only into someone’s head.

*Why it matters:* Teams pay twice when every emergency reinvents the wheel—time now, and mistakes later. Promoting a winning path into the graph is how **today’s fix becomes tomorrow’s default**, which is the whole point of a reusable map vs. a one-off prompt.

---

### Episode 3 — The coupon that almost emailed half the planet

*Later—marketing turns a spreadsheet typo into a nightmare; ops is where the brakes live.*

**Why you’re reading this:** Some actions are too risky to run unattended. A serious workflow builds in **pause points**—it stops and waits until a human approves, especially before mass email or moving serious money.

It happens on a Tuesday when everyone’s already behind. Somebody fat-fingers a cell in the promotions sheet, and the automation cheerfully queues a mass apology email to fourteen thousand people who never asked for one—the kind of mistake that could cost trust before the kettle boils. **Jordan’s** stomach drops when the banner flashes *bulk send pending*.

Then the screen does something humane: it refuses to finish. **Bulk send blocked — approval required.** Fourteen thousand names sit there like a loaded silence; nothing leaves until **Jordan** thumbs **approve** or **cancel**. Jordan can hear their own pulse. The scare is real, but the system won’t complete the risky branch without a person in the loop—no amount of “please double-check” buried in a prompt would have matched that moment.

**The AINL point — what this scene is really about**

*In human terms:* “Be careful” in a document doesn’t compete with adrenaline. What works is **the workflow refusing to finish** until a **person** explicitly approves that risky branch—bulk send, big money, mass outreach. The scare still lands; the blast doesn’t.

*Where this sits in AINL:* This is **control flow** on your **graph**: a **human gate** (approval / checkpoint) on a **branch** before high-impact actions run. It’s part of how AINL handles **safety and governance**—rules live as **steps** the **runtime** enforces, not as vibes in prompt text. Different products phrase it as approvals, **human-in-the-loop**, or **operator checkpoints**; here it’s the same idea: **the map stops until a human says go**.

*Why it matters:* One bad automated send or transfer can cost more than months of “smart” assistance. **Gates in the path** are how organizations keep speed **without** betting the brand on automation sleepwalking through edge cases.

---

### Episode 4 — “What happened to order #4421?”

*Same shop again—this time the bank wants a straight answer, not chat vibes.*

**Why you’re reading this:** Finance—and anyone asking fair questions—needs **the story in order**: what was decided, what pulled which facts in, who approved. When work runs as structured steps, that story becomes a straight line you can read from top to bottom. People call that straight line an **audit trail** in everyday language.

The bank wants chapter and verse on a refund, and **Sam** is on hold with soft jazz bleeding through the phone, laptop fan whining, half a cold sandwich on the desk. They open order **#4421** bracing for chaos—a maze of chat snippets and half-remembered tool answers.

Instead they get something almost old-fashioned: a short trail with timestamps. Damage logged—photos right there. Carrier photos pulled in without Sam begging anyone in Slack. The partial-refund rule applied the way finance actually wrote it. **Jordan** approved at **3:07 p.m.** Sam reads it top to bottom once, exhales, and reads it again to the bank like a receipt you could swear on—not because an assistant was clever that afternoon, but because the steps left footprints.

**The AINL point — what this scene is really about**

*In human terms:* Sam doesn’t need a clever assistant that day—they need a **story they can read aloud** to someone skeptical: what happened, in order, with proof. That’s trust you can’t fake with vibes or screenshots from random chats.

*Where this sits in AINL:* Structured workflows produce **ordered execution**—steps the **runtime** actually ran—which becomes your **audit trail** / **trace**: **who** approved, **what** evidence was attached, **when** it happened. It sits next to **observability** and **compliance** in the big picture: the **graph** makes the sequence explicit, so **replay** isn’t archaeology.

*Why it matters:* Banks, regulators, angry customers, and your own future self all ask “what happened?” If the answer is only “the model said something,” you’re exposed. If the answer is a **step-by-step record**, you can **defend, debug, and improve** the operation without myth-making.

---

### Episode 5 — When the carrier API stops responding

*Back on Dev’s bench—the outside world flakes, and the customer shouldn’t be the first to feel it.*

**Why you’re reading this:** Real shops plug into **outside computer systems**—shipping trackers, payments, email—and those systems fail. Sound design means you **decide in advance what happens** when the connection flakes: try again, breathe, try once more, then fall back to an honest customer message, ping a human, and leave a timestamp finance can find later.

**Dev** turns on live tracking for a shipment that already has enough anxiety baked in. The carrier doesn’t say “lost”—it returns timeouts and error codes that mean nothing friendly on a Friday afternoon. Dev has imagined this failure; what they couldn’t stand was customers imagining it first.

So the shop doesn’t freeze and it doesn’t reflex-refund the internet. The workflow bumps the carrier again, waits, tries once more—still dead—then slips into the branch everyone agreed on when things were calm: send the steady **we’re on it** note from the approved template, text **Jordan** so a human knows before Instagram does, log the incident where **Sam** can see it Monday. Dev swears softly at the screen—the **adapter** misbehaved—but nobody had to invent the backup in a panic; the backup was already written down.

**The AINL point — what this scene is really about**

*In human terms:* The outside world (carriers, banks, inboxes) **will** flake. The question isn’t whether you’ll get an error—it’s whether your team **already agreed** what “try again,” “tell the customer,” and “wake a human” mean **before** anyone is shaking.

*Where this sits in AINL:* Real systems talk to the world through **adapters** (controlled tool connections—HTTP APIs, email, etc.). When an adapter fails, good design is **branches** on the **graph**: **retry**, **backoff**, **fallback message**, **escalate**, **log**—chosen ahead of time and executed by the **runtime**. That’s **resilience** in the map, not improvisation in the panic minute.

*Why it matters:* Customers and finance feel chaos first when your tool quiet-quits or your staff invents policy under stress. **Deciding failure behavior in the workflow** keeps damage bounded and makes outages **boring to explain** instead of heroic firefighting every time.

---

**What next:** The same ideas show up with module vocabulary in **COMPLETE-COURSE.md** modules **7, 8, 13, 14, 15**—memory, GraphPatch, safety rails, audit trails, graceful failure. For **terms without fiction**, keep **[CHEAT-SHEET.md](./CHEAT-SHEET.md)** open—the three-layer story (**write/govern → compile/check → run**) is the frame these episodes plug into.
