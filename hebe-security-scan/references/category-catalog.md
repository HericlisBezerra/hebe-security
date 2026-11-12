# HeBe category catalog

> Every "How to reproduce" step below runs under the execution and secrecy contract in
> `SKILL.md`: local, fixture or disposable staging with fictitious data only; no real
> credential, paid quota, real data or published environment; secrets reported by location and type, never value.

Read for an explicit HeBe Baseline or when category selection is unclear.
For Change/Release, open only the relevant category references.

The categories are grouped into five blocks below. The **grouping is the reading order**; the **number is a stable ID** and never changes, so a category added later can appear inside its block while keeping the ID it was born with. Do not renumber.

### A · Exposure and access — who can get in

| # | Category | Reference |
|---|---|---|
| 1 | **Secrets & environment variables** | `references/01-secrets-and-env.md` |
| 2 | **Access control / IDOR** | `references/02-access-control.md` |
| 3 | **Database rules — Supabase RLS · Firebase · Convex** | `references/03-database-rules.md` |
| 18 | **Sensitive data at rest** — encryption, key custody, backups, logs | `references/18-data-at-rest.md` |
| 4 | **Authentication & session** | `references/04-authentication-session.md` |
| 5 | **Hidden public endpoints** (Server Actions, route handlers) | `references/05-public-endpoints.md` |

### B · Logic flaws — what they can do once in

| # | Category | Reference |
|---|---|---|
| 6 | **Race conditions** | `references/06-race-conditions.md` |
| 7 | **Input validation** | `references/07-input-validation.md` |
| 8 | **Injection** — SQL, XSS, SSRF, command, template, ORM | `references/08-injection.md` |
| 9 | **Mass assignment** | `references/09-mass-assignment.md` |
| 10 | **Business logic** | `references/10-business-logic.md` |

### C · Abuse and economics — what it costs you

| # | Category | Reference |
|---|---|---|
| 11 | **Rate limiting, bot abuse & billing** | `references/11-rate-limiting.md` |
| 12 | **Payments** | `references/12-payments.md` |
| 13 | **AI / LLM integration** | `references/13-ai-llm.md` |

### D · Platform

| # | Category | Reference |
|---|---|---|
| 14 | **Mobile** (React Native / Expo) | `references/14-mobile.md` |

### E · Infrastructure and supply chain — what shipped, not what was written

| # | Category | Reference |
|---|---|---|
| 15 | **Config, headers & CORS** | `references/15-config-headers-cors.md` |
| 16 | **Deployment & environments** | `references/16-deployment.md` |
| 17 | **Dependencies** | `references/17-dependencies.md` |

Block **E** is also where **runtime mode** pays off most — those three are the categories where the code can be right and the deployed app still wrong. See *Runtime mode* below.
