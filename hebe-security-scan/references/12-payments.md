# Payment Security (Stripe & Others)

## Never Trust Client-Submitted Prices

The #1 payment vulnerability in vibe-coded apps: the price comes from the client. An attacker can set any amount, including $0.

### How the attacker exploits it

- Intercepts or crafts the checkout request and overwrites `price` / `unit_amount` (or product name) in the request body before it reaches the server, buying anything for whatever amount they choose — including zero.

### Where to look in the code

- Any checkout/session-creation handler that reads a price, amount, or `price_data` directly from `req.body` instead of looking it up server-side from the database or a Stripe Price ID.

```typescript
// BAD: price comes from the request body
const session = await stripe.checkout.sessions.create({
  line_items: [{
    price_data: {
      currency: 'usd',
      unit_amount: req.body.price, // attacker controls this
      product_data: { name: req.body.name },
    },
    quantity: 1,
  }],
});

// GOOD: look up the price server-side
const product = await db.products.findUnique({ where: { id: req.body.productId } });
if (!product) return new Response('Not found', { status: 404 });

const session = await stripe.checkout.sessions.create({
  line_items: [{ price: product.stripePriceId, quantity: 1 }],
});
```

### How to reproduce

- Open devtools/proxy (e.g., Burp/mitmproxy) on the checkout flow, modify the `price`/`unit_amount`/`productId` field in the outgoing request, and confirm the server accepts the attacker-supplied value instead of rejecting or re-deriving it.

### Fix

Use Stripe Price IDs (created via the Stripe dashboard or API) rather than constructing prices from your database. This way, prices are defined in Stripe and can't be manipulated. Never trust a price, amount, or currency value sourced from client input — always resolve it server-side.

## Webhook Signature Verification Requires the Raw Body

Stripe webhooks must have their signatures verified. This requires the **raw request body** — parsing the body as JSON first destroys the signature.

### How the attacker exploits it

- Sends a forged webhook payload (e.g., fake `checkout.session.completed` or `invoice.paid` event) directly to the webhook endpoint. If the body was already parsed as JSON before signature verification (or verification is missing/broken), the forged event is accepted and the attacker gets access/entitlements without ever paying.

### Where to look in the code

- Express: check whether the webhook route uses `express.raw()` and whether a global `express.json()` middleware runs before it on the same path (which would corrupt the raw body needed for signature verification).
- Next.js App Router: check whether the webhook route handler calls `request.json()` instead of `request.text()` before passing the body to `stripe.webhooks.constructEvent`.

```typescript
// Express: webhook route MUST use express.raw() BEFORE express.json()
app.post('/webhook', express.raw({ type: 'application/json' }), (req, res) => {
  const sig = req.headers['stripe-signature'];
  const event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
  // ... handle event
});

// Next.js App Router: use request.text(), NOT request.json()
export async function POST(request: Request) {
  const body = await request.text();
  const sig = request.headers.get('stripe-signature')!;
  const event = stripe.webhooks.constructEvent(body, sig, webhookSecret);
  // ... handle event
}
```

### How to reproduce

- Send a POST request to the webhook endpoint with an arbitrary/forged payload and a missing or invalid `stripe-signature` header (or no header at all) and confirm whether `constructEvent` still succeeds or the event still gets processed. Also check whether a global body-parsing middleware runs ahead of the raw-body handler on that route.

### Fix

- Express: mount `express.raw({ type: 'application/json' })` on the webhook route before any global `express.json()` middleware applies to it.
- Next.js App Router: read the body with `request.text()`, never `request.json()`, before verifying.
- Always verify with `stripe.webhooks.constructEvent(rawBody, signature, webhookSecret)` and reject on failure.

## Subscription Status Validation

Check subscription status **server-side on every protected request** using your database (kept in sync via webhooks). Do not rely on:
- A cached session value from login time
- A client-side flag
- A JWT claim that was set at token creation and never refreshed

Subscriptions can be cancelled, expire, or change tier at any time. Your database (updated via webhooks) is the source of truth.

### How the attacker exploits it

- Cancels their subscription (or lets it expire) but keeps using a still-valid session/JWT that was issued while the subscription was active, since the server never re-checks current status against the database and instead trusts the stale cached/session/token value.

### Where to look in the code

- Any authorization check for paid features that reads subscription status from `req.session`, a JWT claim, or a value fetched once at login — instead of querying the database (which the webhook handler updates) on each protected request.

### How to reproduce

- Subscribe, capture the session/JWT, then cancel the subscription via Stripe (or simulate the `customer.subscription.deleted`/`updated` webhook) and confirm whether the existing session/JWT still grants access to paid features without a fresh server-side check.

### Fix

Validate subscription status server-side on every protected request against the database, which is kept current via webhook handlers (`customer.subscription.updated`, `.deleted`, `invoice.payment_failed`, etc.). Never trust a cached session value, client-side flag, or an old JWT claim for entitlement decisions.

## Checkout Session Metadata

Validate that checkout session metadata (user ID, plan, etc.) was set **server-side** when creating the session, not passed from the client. If metadata comes from the client, an attacker can claim to be a different user or select a different plan.

### How the attacker exploits it

- Submits a checkout request with a manipulated `metadata.userId` or `metadata.plan` field, so that when the webhook later processes the completed payment, it credits the wrong account or grants a plan/tier the attacker never paid for.

### Where to look in the code

- The checkout-session creation call — confirm `metadata` (user ID, plan, etc.) is populated from the authenticated server-side session/context, not echoed back from `req.body`.
- The webhook handler that reads `event.data.object.metadata` — confirm it trusts that metadata as authoritative without cross-checking against the authenticated user who initiated the session.

### How to reproduce

- Attempt to include a `metadata` object (or override its fields) in the client request that creates the checkout session, and check whether the server passes it through unmodified to Stripe instead of deriving it independently from the authenticated user's identity.

### Fix

Set checkout session metadata entirely from server-side, authenticated context (the logged-in user's ID, the plan they're entitled to purchase) — never accept or merge metadata values sent from the client.

## Cross-Cutting Payment Concerns (Any Provider)

- **Stripe:** verify webhook signatures (`stripe.webhooks.constructEvent`). Never trust a value coming from the client — confirm it via the API. Use idempotency keys. Use Stripe Radar for fraud detection.
- **Internal balance / credit systems:** treat these as the #1 target for race conditions and business-logic abuse (double-spend, concurrent withdrawal requests, negative balances). Use atomic operations, database constraints, and holds on withdrawals.
- **Mercado Pago / Pagar.me and similar providers:** same logic applies — validate the IPN/webhook notification against the provider's source of truth, never trust the client-side redirect as proof of payment.

### How the attacker exploits it

- Fires multiple concurrent requests against a balance/credit-spending endpoint (double-spend race) before the first debit commits, ending up with more credit or a negative balance than should be possible.
- Treats a successful client-side redirect after payment (e.g., Mercado Pago/Pagar.me return URL) as proof of payment and grants access without confirming the transaction server-side via the provider's IPN/webhook.

### Where to look in the code

- Balance/credit debit or withdrawal logic — is it wrapped in an atomic transaction / row lock / constraint, or a plain read-then-write that's vulnerable to concurrent execution?
- Any code path that grants access or marks an order "paid" based solely on the client landing on a "success" redirect URL, rather than a verified webhook/IPN callback.

### How to reproduce

- Fire two or more simultaneous requests against the spend/withdraw endpoint for the same account and check whether both succeed when only one should (balance goes negative or below zero without being blocked).
- Navigate directly to the payment provider's "success" redirect URL without completing an actual payment, and check whether the app grants access anyway.

### Fix

- Wrap balance-affecting operations in atomic transactions with database constraints (e.g., `UPDATE ... WHERE balance >= amount`) or row-level locks, plus holds on pending withdrawals.
- Never grant access, mark orders paid, or credit accounts based on a client-side redirect alone — always confirm via the provider's verified webhook/IPN and cross-check against the provider's API when in doubt.
- Use idempotency keys on payment-creating requests to avoid duplicate charges on retry.
