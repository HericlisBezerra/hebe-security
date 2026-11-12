# Race Conditions (Concurrency)

**Where AI-generated code most often fails, and where the real financial damage happens.** The check and the action happen in separate steps; N parallel requests all pass the check before any one of them has a chance to act on it.

## Targets

- **Money:** purchase, withdrawal, refund, transfer, applying a coupon, affiliate commission.
- **Toggles with a side effect:** like, follow, invite, vote.
- **Limits:** stock/inventory, coupon usage (one-time), slots, quota.
- **Uniqueness:** username/slug/email during concurrent signup.

## Classic exploitation

Buy 3 courses at the same time → 2 succeed but the balance is only debited once → refund both purchases → the balance goes up. **Infinite money.** Or: an affiliate buys their own course using their own coupon, withdraws the commission, then requests a refund within the window — the "same-IP buys and refunds" pattern from the real-world case this playbook was built from.

A concrete real-world pattern seen in the wild: a platform with an affiliate program let a single user (1) sign up as an affiliate, (2) generate their own coupon, (3) buy their own course using that coupon, (4) withdraw the affiliate commission for that sale, and (5) request a refund within the 30-minute refund window — netting free money with no manual detection catching it, because none of the individual steps look wrong in isolation.

## Where to look in the code

- Any "read balance/state → check condition → write new state" sequence that isn't wrapped in a single atomic operation or transaction with a lock.
- Financial operations (purchase, withdrawal, refund, transfer).
- Toggles with side effects (like, follow, invite).
- Unique constraints (username, coupon) not enforced at the database level.
- Stock/balance/usage counters updated via read-modify-write instead of an atomic decrement.

## How to reproduce

```bash
# 10 identical requests in parallel
# local or disposable staging only, with a test user and fictitious balance
seq 10 | xargs -P10 -I{} curl -s -X POST http://localhost:3000/api/compra \
  -H "Authorization: Bearer $TOKEN" -d '{"item_id":1}'
# then: check the final state. Did it count 1 or 10? Does the balance add up?
```

```js
await Promise.all(Array(20).fill(0).map(() =>
  fetch('/api/like',{method:'POST',headers:H,body:JSON.stringify({postId:1})})))
```

Node variant for a purchase-style endpoint:

```ts
await Promise.all(Array(10).fill().map(() =>
  fetch('/api/like', { method: 'POST', body: JSON.stringify({postId: 1}) })
))
// Then verify: was only 1 like actually counted?
```

## Fix

- **Transaction with a lock** (`SELECT ... FOR UPDATE` / `Serializable` isolation level) wrapping the check *and* the action as a single atomic unit.
- **Atomic database operation** (`UPDATE ... WHERE balance >= x`, atomic decrement) instead of a read-modify-write round trip.
- **Constraint as the final safety net:** `CHECK (balance >= 0)`, `UNIQUE`, conditional decrement — the database refuses the write outright if it would violate the invariant, even if the application logic above it has a race.
- **Idempotency key** on financial operations (the same key always resolves to the same operation — replays don't double-execute).

Example transaction pattern (Prisma):

```ts
await prisma.$transaction(async (tx) => {
  const account = await tx.account.findUnique({
    where: { id: accountId },
    // Postgres: FOR UPDATE — exclusive lock
  })
  if (account.balance < amount) throw new Error('insufficient')
  await tx.account.update({
    where: { id: accountId },
    data: { balance: { decrement: amount } }
  })
  await tx.purchase.create({ data: { /* ... */ } })
}, { isolationLevel: 'Serializable' })
```

Example constraint as final safety net:

```sql
alter table accounts add constraint balance_non_negative check (balance >= 0);
```

If the `UPDATE` would push the balance negative, the database rejects it outright — this is the last line of defense even if the application-level transaction logic has a gap.
