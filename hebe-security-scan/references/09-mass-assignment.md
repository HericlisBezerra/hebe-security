# Mass Assignment

## Spreading the request body into create/update

### How the attacker exploits it
When a handler passes the raw request body straight into a database create/update call, the attacker can add fields the API was never meant to expose — `role: "admin"`, `isAdmin: true`, `credits: 99999`, `verified: true`, `balance: 9999` — and the ORM happily writes them because nothing filtered the object first. This works even when the UI never shows those fields: the attacker isn't using the UI, they're calling the API directly with a crafted body.

### Where to look in the code
- `Model.create(req.body)`, `Model.update(req.body)` / `update(**data)` patterns.
- `Object.assign(user, body)` or any object-spread of unvalidated input into an entity (`{ ...user, ...req.body }`).
- Absence of "strong params" / an explicit allowlist layer between the request and the persistence call.
- Any endpoint whose only gate is authentication, with no field-level authorization on write.

### How to reproduce
Send a normal-looking update request but add extra fields the endpoint shouldn't accept, e.g.:
```json
PATCH /api/users/me
{ "name": "Alice", "role": "admin", "credits": 99999, "isAdmin": true }
```
If the response (or a follow-up read) shows `role`/`credits`/`isAdmin` changed, the endpoint is vulnerable to mass assignment.

### Fix
Never spread request bodies directly into database operations. Pick only the fields the endpoint is actually supposed to let the caller change — an explicit allowlist, not a blocklist.

```typescript
// BAD: attacker can add { isAdmin: true, credits: 99999 }
await db.users.update({ where: { id }, data: req.body });

// GOOD: pick only allowed fields
const { name, email } = validated.data;
await db.users.update({ where: { id }, data: { name, email } });
```

This is the same failure whether it shows up as `Model.create(req.body)`, `update(**data)` in a Python/Rails-style handler, or `Object.assign(user, body)` — the fix is always the same: validate first (e.g. with Zod), then construct the write payload from the validated, explicitly-named fields only. Never let user input decide *which* fields get written, only their *values*.
