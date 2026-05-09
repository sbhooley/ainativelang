# Who does what? (No jargon RACI)

“RACI” is consultant-speak for **who’s responsible, who approves, who gets consulted, who must be informed.** Here’s a plain version for **who touches an AINL workflow in real life** — who authors the **graph**, who runs the **runtime**, who owns updates after policy changes.

**Sunrise Ceramics** below is the same cast as the story file: it labels **roles**, not a separate plot.

---

### The roles (plain English)

| Role | Job in one breath |
|------|---------------------|
| **Author / maintainer** | Owns the **map**: steps, branches, tool hooks, updates when policy changes. Often product, ops, or a technical teammate—**someone must own it.** |
| **Runner / operator** | Triggers runs, handles day exceptions, uses **Approve** when the map pauses. Often Jordan-like frontline ops. |
| **Approver** | Says **yes/no** on sensitive moves (refunds, bulk email, big credits). Maybe Jordan + Sam; maybe a manager rule. |
| **Governance / risk** | Sets boundaries: what tools exist, what data can leave, retention—usually infrequent touch unless something breaks. |
| **Customer / auditor** | Doesn’t edit the map—**asks “what happened?”** Finance, legal, angry customer with rights. The map should answer them. |

**Consulted / Informed** — People who need a heads-up (support lead, legal on template changes) but aren’t clicking **Approve** every day.

---

### Sunrise Ceramics — who plays which part?

| Person | Role | Example |
|--------|------|---------|
| **Jordan** | Runner + often Approver | Daily refunds, packaging exceptions, taps **Approve** before mass email. |
| **Sam** | Governance-adjacent + auditor mindset | Asks for **timelines** for the bank; pushes for clearer refund branches. |
| **Dev** | Practical maintainer of shipping steps | When carriers change APIs, someone updates the **fragile export** path—or the shop ships lies. |
| **Ms. Rivera** | Customer | Never edits the map—benefits when **memory** and **packaging rules** fire correctly. |

---

### RACI-style grid (example: “International fragile refund”)

Use this as a **template**; swap names for your org.

| Activity | Author | Runner | Approver | Informed |
|----------|--------|--------|----------|----------|
| Update workflow map after carrier change | Dev + Jordan | — | Jordan | Sam |
| Run refund / partial credit | — | Jordan | Jordan if over threshold $X | Sam if over threshold $Y |
| Promote **Fragile Export v3** after a win | Jordan | — | Jordan | Dev, Sam |
| Bulk customer email | Dev (map) | Jordan | Jordan **required** | Sam |

*(“Author” can be split: policy owner vs person who edits tooling—what matters is **no orphan maps**.)*

---

### Failure mode to avoid

**Everyone reads the workflow; nobody owns updates.**  
Then reality shifts (new refund policy) and the map becomes folklore.

**Fix:** name **one** maintainer on paper—even part-time.

---

### Takeaway

AINL doesn’t replace **ownership**. It makes ownership **visible**: who wrote the path, who can approve, who must be told when the path changes.
