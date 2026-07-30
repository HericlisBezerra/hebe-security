# Rate Limiting & Abuse Prevention

## Missing Rate Limits on Sensitive Endpoints

Every one of these endpoints needs rate limiting. AI assistants almost never add it:

- **Auth endpoints** — login, register, password reset, OTP verification, magic link. Without limits, attackers can brute-force passwords or enumerate accounts.
- **AI API calls** — Any endpoint that calls OpenAI, Anthropic, or similar. A single user can drain your entire monthly budget in minutes.
- **Email / SMS sending** — Attackers can use your app as a spam relay.
- **File processing** — Upload, resize, convert. CPU-intensive operations without limits enable denial-of-service.
- **Webhook-like endpoints** — Anything accepting external input at scale.

### How the attacker exploits it

- Scripts a brute-force or credential-stuffing loop against `/login`, `/register`, `/reset-password`, `/verify-otp`, or `/magic-link` with no backoff, since nothing throttles repeated attempts.
- Hammers an AI-backed endpoint (chat, generation, summarization) in a tight loop to run up the victim's OpenAI/Anthropic bill or exhaust a shared quota.
- Uses an email/SMS-sending endpoint (invites, notifications, "resend code") as a free spam relay.
- Sends a flood of upload/resize/convert requests to burn CPU and force a denial-of-service.
- Floods any endpoint that accepts bulk external input (webhook receivers, public form submissions) with no per-source cap.

### Where to look in the code

- Auth routes (`/login`, `/register`, `/reset-password`, `/otp`, `/magic-link`) for any rate-limiting middleware or its absence.
- AI proxy routes/handlers that call an LLM provider.
- Mail/SMS sending routes (invite, resend-code, contact-form, notification triggers).
- Upload/processing routes (image resize, file conversion, PDF generation).
- Any route accepting third-party or public input at scale.

### How to reproduce

- Fire N rapid sequential requests (e.g., with `curl` in a loop or a simple script) at the auth or AI endpoint and confirm none are rejected with `429`.
- Check whether the same request succeeds indefinitely regardless of volume from a single IP or a single authenticated user.

### Fix

Add rate limiting at the endpoint (see Implementation Pattern below) using a per-IP and per-user combined strategy, tuned per endpoint sensitivity (auth stricter than general API traffic).

## Don't Store Rate Limits in Public Tables

If rate limit counters live in a Supabase public table, users can reset their own counters via the REST API.

### How the attacker exploits it

- Reads their own rate-limit counter row through the PostgREST-exposed public table (via the `anon`/`authenticated` key) and issues a `DELETE` or `UPDATE` against it, resetting their own limit and bypassing throttling entirely.

### Where to look in the code

- Any table named like `rate_limits`, `request_counts`, `login_attempts` that lives in the Supabase `public` schema and is queried/mutated via the client-side Supabase SDK.
- Row Level Security policies on that table — if the counter can be read or written by `authenticated`/`anon` roles, it's exploitable.

### How to reproduce

- With a normal user's anon/auth key, call the Supabase REST endpoint for the rate-limit table directly (e.g., `PATCH`/`DELETE` on `/rest/v1/rate_limits?user_id=eq.<self>`) and confirm the counter can be modified or cleared.

### Fix

Use one of:

- **Upstash Redis** — Serverless Redis with built-in rate limiting primitives
- **Private schema table** — Not exposed via PostgREST
- **Middleware-level limiting** — At the edge or API gateway
- **In-memory stores** — For single-server deployments (Redis for multi-server)

## Combine Per-IP and Per-User Limiting

- IP-only limits are defeated by rotating IPs (trivial with VPNs or botnets)
- User-only limits are defeated by creating new accounts
- Use both together for effective protection

### How the attacker exploits it

- If only IP-based limiting is in place, rotates IPs via VPN or a botnet to reset the counter on each request.
- If only user-based limiting is in place, creates disposable new accounts (email aliasing, throwaway signup) to reset the counter each time.

### Where to look in the code

- Rate-limiting logic that keys solely on `req.ip` or solely on `userId`, without combining both dimensions.

### How to reproduce

- Simulate requests from multiple IPs against a user-only-limited endpoint (or multiple fresh accounts against an IP-only-limited endpoint) and confirm the limit resets each time.

### Fix

Key the rate limiter on both IP and user ID together (or apply both limits independently and enforce whichever is hit first), so defeating one dimension alone doesn't bypass protection.

## Billing Protection

- Set billing alerts on every cloud provider (AWS, GCP, Vercel, etc.)
- Set **hard spending caps** on AI API providers (OpenAI, Anthropic)
- Use per-user usage quotas with hard limits, not just soft warnings
- Monitor for anomalous usage patterns (sudden spikes, requests at odd hours)

### How the attacker exploits it

- Exploits an unthrottled AI or cloud-resource endpoint to generate massive, unexpected provider bills before anyone notices, since there are no hard caps or anomaly alerts to stop it early.

### Where to look in the code

- Provider dashboards/config for AWS, GCP, Vercel, OpenAI, Anthropic — check whether billing alerts and hard spending caps are actually configured (not just "available").
- Application-level usage tracking — is there any per-user quota enforcement, or does every request just pass through unmetered?

### How to reproduce

- Attempt a sustained burst of requests against the AI/cloud-backed endpoint and check whether anything (soft warning, hard block, alert) triggers before the request volume becomes expensive.

### Fix

- Set billing alerts on every cloud provider (AWS, GCP, Vercel, etc.)
- Set hard spending caps on AI API providers (OpenAI, Anthropic)
- Use per-user usage quotas with hard limits, not just soft warnings
- Monitor for anomalous usage patterns (sudden spikes, requests at odd hours)

## Implementation Pattern

```typescript
// Example: rate limiting with Upstash Redis
import { Ratelimit } from '@upstash/ratelimit';
import { Redis } from '@upstash/redis';

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(10, '1 m'), // 10 requests per minute
});

export async function POST(request: Request) {
  const ip = request.headers.get('x-forwarded-for') ?? '127.0.0.1';
  const { success } = await ratelimit.limit(ip);
  if (!success) {
    return new Response('Too many requests', { status: 429 });
  }
  // ... handle request
}
```
