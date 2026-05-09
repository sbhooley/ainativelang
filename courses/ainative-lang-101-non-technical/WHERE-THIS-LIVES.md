# Where does this actually happen?

You can understand AINL **without installing anything**. This whole folder is proof: plain words, stories, a glossary.

The stories exist to show **where the graph lives emotionally**—who maintains the **compiled workflow**, who runs the **runtime**, who sees the **audit trail**. They are not a substitute for the stack below.

When someone asks, **“Where do I click?”**, the honest answer is: **it depends on your stack.** AINL is the **workflow language + compiler + runtime idea**; different products wrap it differently.

---

### If you’re **not** building software

You usually **don’t** open a code editor. You care that:

- Someone on your team (or a vendor) **maintains the map** — the steps, approvals, tools.  
- Your **agent or automation product** can **run** structured workflows **reliably**.  
- There is a **place** to see what happened when customers or finance ask.

Ask vendors or internal builders: **“Can we express this as an explicit workflow with approvals and history—not only prompts?”** That’s the spirit of AINL even if they use another label.

---

### If you **are** curious where builders work (high level)

Typical layers (names vary by product):

| Layer | Plain English |
|-------|----------------|
| **Authoring** | Someone writes or generates `.ainl` (or uses tooling that outputs it). |
| **Compile / validate** | The system checks the plan before it runs—preflight, not guesswork. |
| **Runtime** | The engine walks the graph and calls tools through **adapters**. |
| **Host** | Chat apps, schedulers, agent desktops, or services that **trigger** runs and show results. |

Open-source / docs-oriented workflows often use the **AINL CLI** (`ainl validate`, `ainl run`, etc.) in developer setups. **Embedded agents** (for example desktop agent systems) may run compiled workflows **behind the scenes** so operators see buttons and timelines—not raw graphs.

---

### One sentence for meetings

**“AINL is the structured workflow layer; your product is where people live—but the map shouldn’t live only inside a giant prompt.”**

---

### Sunrise Ceramics angle (memory hook)

**Jordan** doesn’t care about file extensions. They care that **Ms. Rivera’s packaging rule** and **Black Friday approval gates** live in a **system** someone can audit—not in Jordan’s head at 11 p.m.

In AINL terms: **memory** and **permissioned branches** belong in the **workflow** (and its **runtime** history), not only in chat scrollback.

That’s what “where it lives” means emotionally: **operational truth**, not a paragraph in a chat box.
