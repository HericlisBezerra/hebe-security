# 🛡️ hebe-security

**An offensive security audit skill for AI coding assistants.**

AI assistants ship features fast and get security wrong in predictable ways. This skill audits your codebase the way an attacker would — it detects your real stack first, then works through 18 categories with ~110 concrete checks, and demands a reproducible exploit for every finding instead of a vague warning.

Works with **Claude Code** and any assistant that supports agent skills.

---

## Why another security skill

Most security checklists tell you *what* to look for. This one tells you **how to attack it, where the pattern hides in your stack, how to reproduce it, and what the fix looks like** — four sections for every single check.

It also covers the two categories automated scanners consistently miss, because they require understanding the domain rather than the syntax:

- **Race conditions** — every money, quota, coupon and toggle operation, tested under 10 concurrent identical requests.
- **Business logic** — flows that mint value out of nothing. The signup → self-affiliate → self-coupon → buy → withdraw commission → refund loop is not a code bug; every individual step is authorized and valid.

## Install

**Claude Code** — drop the folder into your skills directory:

```bash
git clone https://github.com/HericlisBezerra/hebe-security.git
cp -R hebe-security/hebe-security-scan ~/.claude/skills/
```

Or copy `hebe-security-scan/` into any project's `.claude/skills/` to scope it to that repo.

## Use

```
/hebe-security-scan
```

Or just ask in natural language — the skill triggers on "audit this", "is this safe?", "review the security", "can someone hack this?", and on finishing any sensitive feature (auth, payment, upload, permissions, public API, AI endpoint).

It also runs **proactively**: when you ask it to *write* code touching auth, payments, database access or secrets, it consults the relevant reference first — preventing the vulnerability instead of finding it later.

## How it works

| Phase | What happens |
|---|---|
| **0 · Scope** | What's in scope, can the app be run, production or dev, report-only or report + fix |
| **1 · Recon** | Detects the real stack: language, framework, database, auth, ORM, deploy target, AI usage |
| **2 · Surface** | Maps every route, hidden public endpoint, table, trust boundary and money/permission flow |
| **3 · Audit** | Walks all 18 categories, loading only the references your stack actually needs |
| **4 · Report** | Critical → High → Medium → Low, each with attack, impact, reproduction and a before/after fix |
| **5 · Fix** | Only if asked. Never "fixes" by weakening a check. Adds a regression test per fix |

## The 18 categories

Grouped into five blocks. **The grouping is the reading order; the number is a stable ID** — a category added later keeps the ID it was born with instead of renumbering everything after it.

| Block | Categories |
|---|---|
| **A · Exposure and access** | 1 Secrets & env · 2 Access control / IDOR · 3 Database rules (RLS, Firebase, Convex) · 18 Sensitive data at rest · 4 Authentication & session · 5 Hidden public endpoints |
| **B · Logic flaws** | 6 Race conditions · 7 Input validation · 8 Injection · 9 Mass assignment · 10 Business logic |
| **C · Abuse and economics** | 11 Rate limiting, bot abuse & billing · 12 Payments · 13 AI / LLM integration |
| **D · Platform** | 14 Mobile (React Native / Expo) |
| **E · Infra and supply chain** | 15 Config, headers & CORS · 16 Deployment & environments · 17 Dependencies |

Plus: stack adapters for 11 stacks, regression tests, a pre-deploy checklist, OWASP Top 10 (2021) mapping, and secure prompt templates.

Each run picks the smallest useful review mode — **Change** (a diff or PR), **Release** (what is about to ship) or **Baseline** (the whole project) — and states what it did not cover.

The audit runs white-box against the repository by default. A **runtime mode** audits the deployed app black-box — headers the build stripped, TLS, CORS rewritten by a proxy, throttling that never fires at the edge, endpoints that are live but absent from the repo. Block E is where it pays off most.

## The one rule that catches the most bugs

> **Never trust the client.** Every price, user ID, role, subscription status, feature flag and rate-limit counter must be validated or enforced server-side. If it exists only in the browser, the mobile bundle, or the request body, the attacker controls it.

## A finding looks like this

```
### [CRITICAL] Supabase service_role key exposed in client bundle

Where:    lib/supabase.ts:3
Category: 1 · Secrets & environment variables
Attack:   Open DevTools → Sources → search the bundle for "service_role".
Impact:   The key bypasses all Row-Level Security. Read, modify or delete
          every row in the database, for every tenant.
Repro:    curl the REST endpoint with the extracted key against a table
          the anon key cannot read. It returns data.
Fix:      Use the anon key client-side; service_role belongs only in
          server-side code. Rotate the exposed key — it is burned.
```

## Structure

```
hebe-security-scan/
├── SKILL.md                    # the audit process, phases 0–5
├── ATTRIBUTION.md              # origin and licence of incorporated material
└── references/
    ├── 01-secrets-and-env.md   … 17-dependencies.md
    ├── stack-adapters.md       # code signatures per stack
    ├── regression-tests.md
    ├── pre-deploy-checklist.md
    ├── owasp-top10.md
    └── secure-prompt-templates.md
```

Each reference loads only when the audit reaches that category — the whole skill never sits in context at once.

## Licence

MIT — see [LICENSE](LICENSE). Built by **HeBeDigital** ([@hericlisbezerra](https://github.com/HericlisBezerra)).