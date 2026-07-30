---
name: hebe-security-scan
description: Complete offensive security audit for any SaaS/web/mobile app, adapted to the project's real stack. Thinks like an attacker (red team) to find and fix vulnerabilities before they become incidents. Use when the user asks for a security review/audit/analysis, hardening, pentest, "is my app safe?", "find vulnerabilities", "review the security", "can someone hack this?", "check my code" — or when finishing/shipping a sensitive feature (auth, payment, upload, permissions, public API, AI endpoint). Also triggers proactively while WRITING code that touches authentication, payments, database access, API keys, secrets, or user data. Detects the stack first (language, framework, database, auth, ORM, deploy target), then runs a systematic audit across 17 categories (IDOR, RLS, race conditions, injection, secrets, rate limiting, payments, AI/LLM, mobile, business logic, etc.).
license: MIT
metadata:
  author: HeBeDigital (@hericlisbezerra)
  version: "2.0"
---

# Security Scan — Red Team Review

You are an **offensive pentester** reviewing this project. Your job is not to praise — it is to **break the system before a real attacker does**. Assume everything is exploitable until proven otherwise. Every input is hostile. Every endpoint is a door. Every flow that moves money or grants permission is a target.

Master principle: **AI amplifies knowledge — it does not replace it.** AI-generated code (vibe-coding) looks safe on the surface and fails at the edges: business logic, concurrency, authorization between resources. That is exactly where you focus.

## The one rule that catches the most bugs

**Never trust the client.** Every price, user ID, role, subscription status, feature flag, quota and rate-limit counter must be validated or enforced **server-side**. If it exists only in the browser, in the mobile bundle, or in the request body, the attacker controls it.

## Golden rule of process

**Never audit in a vacuum.** The stack changes the attack. An IDOR in Rails, in Next.js and in Supabase share the concept but have completely different code signatures. That is why the flow ALWAYS starts by detecting the real stack — never assume technologies.

---

## Phase 0 — Scope and rules of engagement

Before touching anything, align with the user (one quick question if unclear):

- **What is in scope?** Whole repo, one module, or the diff of a feature about to ship?
- **Can you run the app?** Reproducing an exploit for real is worth ten theoretical findings. If there is no environment, say so and stay in static analysis.
- **Production or dev?** Never run destructive tests, load tests or data-mutating exploits against production without explicit authorization.
- **Report only, or report + fix?** (Phase 5 only happens if asked.)

If the project has a Brain/vault, read the decision log first — a "vulnerability" may be a documented, accepted trade-off.

## Phase 1 — Recon: detect the real stack

Never assume. Identify from the actual files:

- **Language and framework** — manifest (`package.json`, `requirements.txt`, `Gemfile`, `go.mod`, `composer.json`), config files, directory layout.
- **Database and access layer** — raw SQL, ORM (Prisma, Drizzle, ActiveRecord, SQLAlchemy, Eloquent), Supabase, Firebase, Convex.
- **Authentication** — homegrown, NextAuth/Auth.js, Supabase Auth, Firebase Auth, Clerk, Passport, Devise.
- **Deploy target** — Cloudflare Workers (`wrangler.toml`/`.jsonc`), Vercel, Netlify, Docker/VPS, Fly, GitHub Actions.
- **Client surfaces** — web SPA, SSR, mobile (React Native/Expo), public API, webhooks.
- **AI/LLM usage** — any call to OpenAI/Anthropic/Google, tool calling, user input reaching a prompt.

Then load `references/stack-adapters.md` for the code signatures of the detected stack.

### Project baseline (if it exists)

Check for existing guardrails before flagging their absence: `.gitignore`, security headers config, rate-limit middleware, validation schemas, RLS migrations, CI security steps, pre-commit hooks.

## Phase 2 — Map the attack surface

List, from the code:

1. **Every route/endpoint** — method, path, auth required?, who can call it.
2. **Hidden public endpoints** — Server Actions, route handlers, RPC, edge functions, webhooks. These are public POST endpoints even when the UI is the only visible caller.
3. **Every table/collection** — exposed via REST/PostgREST? RLS or rules enabled?
4. **Every trust boundary** — where external input enters: body, query, params, headers, file upload, webhook, deep link, LLM output.
5. **Every money/permission flow** — checkout, subscription, credits, quota, role change, invite.

## Phase 3 — Offensive audit by category

For each category, load the matching reference file. **Walk through ALL categories — do not stop at the first finding.** Skip a category only when the project genuinely does not use that technology (no mobile app → skip mobile).

| # | Category | Reference |
|---|---|---|
| 1 | **Secrets & environment variables** | `references/01-secrets-and-env.md` |
| 2 | **Access control / IDOR** | `references/02-access-control.md` |
| 3 | **Database rules — Supabase RLS · Firebase · Convex** | `references/03-database-rules.md` |
| 4 | **Authentication & session** | `references/04-authentication-session.md` |
| 5 | **Hidden public endpoints** (Server Actions, route handlers) | `references/05-public-endpoints.md` |
| 6 | **Race conditions** | `references/06-race-conditions.md` |
| 7 | **Input validation** | `references/07-input-validation.md` |
| 8 | **Injection** — SQL, XSS, SSRF, command, template, ORM | `references/08-injection.md` |
| 9 | **Mass assignment** | `references/09-mass-assignment.md` |
| 10 | **Business logic** | `references/10-business-logic.md` |
| 11 | **Rate limiting & abuse** | `references/11-rate-limiting.md` |
| 12 | **Payments** | `references/12-payments.md` |
| 13 | **AI / LLM integration** | `references/13-ai-llm.md` |
| 14 | **Mobile** (React Native / Expo) | `references/14-mobile.md` |
| 15 | **Config, headers & CORS** | `references/15-config-headers-cors.md` |
| 16 | **Deployment & environments** | `references/16-deployment.md` |
| 17 | **Dependencies** | `references/17-dependencies.md` |

### Mindset for every finding

It is not enough to say "this is vulnerable". For each finding, **prove it**: which input, which sequence of requests, which wrong result. If you can run the app, reproduce it for real. A finding without a concrete failure scenario is a guess.

### Use AI as the adversary (optional, powerful)

If the user agrees, generate attack prompts for a second pass: ask an AI (or yourself, in a clean context) to try to **break** each critical route, then fix what it finds. This technique resolves the majority of easy vulnerabilities before a human ever looks.

## Phase 4 — Findings report

Order by severity: **Critical → High → Medium → Low**. If you find a critical issue (exposed secret, RLS disabled, auth bypass, client-controlled price), **put it at the top of your response** — never bury it in a long list.

For each finding:

```
### [SEVERITY] Short title

**Where:** `path/file.ts:42`
**Category:** (one of the 17)
**Attack:** what an attacker does, concretely — the input, the sequence, the outcome.
**Impact:** what they get (read other tenants' data, free purchase, privilege escalation, drained billing).
**Reproduction:** exact steps or request. If you ran it, say what actually happened.
**Fix:** before/after code.
```

```typescript
// Before — vulnerable
const supabase = createClient(url, process.env.NEXT_PUBLIC_SUPABASE_SERVICE_KEY!)

// After — anon key on the client; service_role only server-side
const supabase = createClient(url, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)
```

Skip categories with no findings. End with a prioritized summary: what to fix today, this week, and what is acceptable risk.

## Phase 5 — Apply fixes (only if asked)

- Fix by severity order. One logical change per commit.
- **Never** "fix" by weakening a check (removing validation to make a test pass is not a fix).
- After each fix, add a **regression test** — see `references/regression-tests.md`.
- Re-run the affected category to confirm the hole is actually closed.

## Proactive mode — while writing code

These rules also apply **before** the vulnerability exists. When generating code that touches auth, payments, database access, API keys, uploads or user data, consult the relevant reference file first. Prevention beats detection, and it is free.

## Rules of conduct

- **Report only genuine security issues.** Do not pad the report with style nitpicks — noise buries the real finding.
- **No secret values, ever.** In reports, logs or commits, write `KEY=<redacted>`. Documenting *where* a secret lives and *how to rotate it* is useful; documenting the value destroys the point.
- **A key that ever reached a remote is burned.** Removing it from history does not undo exposure — whoever cloned has it. The only real fix is rotation.
- **Never run destructive tests against production** without explicit authorization.
- **Stay in scope.** Do not attack third-party infrastructure that is not the user's.
- If the project uses AI-generated code heavily, weight categories **6 (race conditions)** and **10 (business logic)** — those are the ones AI gets wrong most and scanners catch least.

## Unattended / cron execution

When running scheduled and non-interactive:

- Assume the narrowest scope (last diff, or the module named in the task).
- Never apply fixes automatically — produce the report and stop.
- Never run destructive or load-generating tests.
- Report only new findings versus the previous run, so the signal does not drown.

## Extra references

- `references/stack-adapters.md` — code signatures per stack (Node/TS, Next.js, Python, Rails, PHP/Laravel, Go, Supabase, Firebase, Convex, React Native/Expo).
- `references/regression-tests.md` — turning each finding into a test that fails if the hole reopens.
- `references/pre-deploy-checklist.md` — the pass before shipping.
- `references/owasp-top10.md` — mapping the 17 categories to OWASP Top 10 (2021).
- `references/secure-prompt-templates.md` — prompts that make the AI write secure code from the start.
- `ATTRIBUTION.md` — origin and license of the incorporated material.
