# Secure Prompt Templates

Prevention beats detection. The cheapest vulnerability is the one the AI never writes. Paste these into the prompt **before** asking for the feature — not after the bug exists.

## Baseline block — paste into any feature prompt

```
# Non-negotiable security requirements

## Authentication
- Every endpoint that touches user data verifies the session server-side.
- Never trust a client-supplied user ID, role, tier, or permission flag.

## Authorization
- Authentication is not authorization: after confirming WHO the user is,
  confirm they OWN the specific resource being read or written.
- Scope every query by owner (`where: { id, userId: session.user.id }`),
  never fetch-then-compare in application code.

## Input validation
- Validate every external input with a runtime schema (Zod or equivalent)
  at the boundary: route handlers, Server Actions, webhooks, forms, query params.
- TypeScript types are compile-time only — they are not validation.
- Set a maximum length on every string field. Validate uploads by MIME,
  magic bytes and size.

## Secrets
- No credential in source code. Server-side keys never reach the client bundle.
- Nothing secret behind a public prefix (NEXT_PUBLIC_ / VITE_ / EXPO_PUBLIC_ / REACT_APP_).

## Race conditions
- Any operation that spends money, consumes a quota, redeems a coupon or
  flips a limited flag must be safe under 10 concurrent identical requests.
  Use a transaction, a row lock, a unique constraint or an idempotency key.

## Rate limiting
- Auth endpoints, AI calls, email/SMS sending and file processing are rate limited
  per-IP AND per-user. Counters are not stored anywhere the user can write to.

## Required tests
- One test per rule above, written to FAIL if the protection is removed.

## Threats to defend against explicitly
- IDOR: user A reading or modifying user B's resource.
- Privilege escalation via mass assignment (isAdmin, credits, tier in the request body).
- Price/quantity manipulation from the client.
- Replay and concurrency on any financial operation.
```

## Review prompt — make the AI attack its own code

Run this in a **clean context**, after the feature is written:

```
You are an offensive pentester. This code was written by an AI assistant and is
assumed vulnerable. Your goal is to BREAK it, not to praise it.

For each vulnerability you find:
1. Name the exact input or request sequence that exploits it.
2. State what the attacker obtains (data, money, privilege).
3. Show the minimal fix.

Focus first on: authorization between resources (IDOR), concurrency on
money/quota operations, business logic that grants value from nothing,
and any value taken from the client and trusted.

Do not report style issues. Only report what you can demonstrate.
```

## Fix prompt — do not let the fix weaken the check

```
Fix the vulnerability below WITHOUT removing or loosening any existing
validation, and without changing behaviour for legitimate users.
Add a regression test that fails if this fix is reverted.

Vulnerability: <paste finding>
```

## Why this works

The specialist behind the source material resolved the majority of easy vulnerabilities simply by making the AI attack its own system and fixing what it found. The model is good at finding the class of bug it just produced — it only needs to be pointed at the target with an adversarial frame.
