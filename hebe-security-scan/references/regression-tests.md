# Security Regression Tests

The single biggest differentiator between teams that ship secure code and teams that don't isn't raw security knowledge — it's methodology. In a head-to-head experiment pitting several AI-assisted developers against a professional pentester, the developer who broke the problem into small steps and had the AI generate integration tests covering vulnerability scenarios shipped with **zero vulnerabilities** found, while others (without that test discipline) shipped a race condition in a financial transaction, a missing input limit, and hardcoded secrets. The AI itself wasn't the differentiator — the process was, and the process is teachable.

The core idea: after fixing any finding, add a test that **fails if the hole reopens**. A future prompt, refactor, or dependency bump that reintroduces the bug gets caught by CI before it ever reaches a commit, instead of being caught by an attacker in production.

## Turning a finding into a regression test

For every category of vulnerability, there's a mechanical way to express "this must never work again" as an automated test:

1. **IDOR:** authenticate as user A, request a resource belonging to user B → assert **404**.
2. **Auth bypass:** call the endpoint with no token / an invalid token → assert **401**.
3. **Rate limiting:** send N requests in a burst → assert requests past the threshold are blocked (429 or similar).
4. **Race condition:** fire N identical POST requests in parallel against a critical operation → assert exactly **1** effect was applied (1 charge, 1 like, 1 stock decrement — not N).
5. **Mass assignment:** submit `{"role": "admin"}` (or any other privileged field) in a create/update body → assert the field was **ignored**, not applied.
6. **Input limits:** submit a field with 10,000+ characters where the schema caps it lower → assert **400**.
7. **Upload validation:** submit a `.exe` renamed with `Content-Type: image/png` → assert **400** (content-based detection, not extension/MIME trust).
8. **User enumeration:** call `/reset-password` (or `/login`) with an email that doesn't exist vs. one that does → assert the **response is identical** in both cases.
9. **SQL injection:** submit a value containing quotes/SQL comment syntax (`' OR 1=1 --`) → assert it's treated as a literal string, not executed as SQL.
10. **XSS:** submit `<script>alert(1)</script>` in a field that gets rendered elsewhere → assert it renders as escaped text, not as an executing script.

## Requesting these from an AI

Ask explicitly and concretely — vague prompts produce vague (or skipped) tests. Effective phrasing:

```
Generate integration tests covering these scenarios:
1. IDOR: user A tries to edit/delete a resource belonging to user B → 404
2. Auth bypass: calling the endpoint with no token → 401
3. Rate limit: 20 requests in 1s against login → the last ones are blocked
4. Race condition: 10 parallel POST /like requests on the same post → exactly 1 like counted
5. Mass assignment: POST /users with { role: 'admin' } → role is ignored
6. Input limits: a name field with 10,000 chars → 400
7. Upload: a .exe file with Content-Type: image/png → 400
8. Enumeration: /reset-password with a nonexistent email → same response as an existing one
9. SQL: input containing single quotes/comment syntax → treated as a plain string
10. XSS: a post containing <script>alert(1)</script> → rendered as escaped text
```

### Anti-patterns to avoid when prompting for these tests
- "Make sure it's secure" — too vague, gets ignored or produces shallow tests.
- "Don't make mistakes" — too vague.
- Asking without naming the actual routes/scenarios in your app — the AI will invent generic cases instead of covering your real attack surface.

## Reproducing race conditions directly (before writing the test)

A simple way to manually confirm a race condition exists, before encoding it as an automated test:

```bash
# Fire 10 identical requests in parallel
seq 10 | xargs -P 10 -I{} curl -X POST https://api.exemplo.com/compra \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"curso_id": 1}'
# then check final state: was it counted once, or ten times? does the balance add up?
```

```ts
await Promise.all(Array(10).fill(0).map(() =>
  fetch('/api/like', { method: 'POST', body: JSON.stringify({ postId: 1 }) })
))
// then check: was only 1 like actually counted?
```

## Stack and workflow

- **Vitest** or **Jest** — unit + integration tests.
- **Playwright** — end-to-end tests.
- **Supertest** — HTTP-level integration tests.
- **Run in CI before every merge.** This is what let the best-performing developer in the reference experiment ship with zero vulnerabilities: TDD plus AI-generated vulnerability tests that flagged a regression before the commit ever landed, not after an attacker found it.

## Using AI as an adversary, separately from writing tests

Beyond generating regression tests for known findings, open a **separate, clean-context conversation** after the system is otherwise complete and have the AI actively attack it:

```
You are a pentester. Here is the code for my system (or the specification of its routes).
Your mission: find vulnerabilities. Consider:
- IDOR on every route with an :id parameter
- Race conditions in [list the critical routes]
- Authentication bypass
- Business logic (look for flows involving money, permissions, or state)
- Mass assignment
- Injection (SQL, XSS, SSRF, command)
- Input validation

For each vulnerability found, provide:
1. Description
2. Steps to reproduce
3. Impact (critical/high/medium/low)
4. Suggested fix
```

Every finding this adversarial pass turns up should, in turn, get its own regression test using the same mechanical patterns above — closing the loop between "found once" and "can never silently reopen."
