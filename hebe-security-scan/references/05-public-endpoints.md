# Public Endpoints (Server Actions & Route Handlers)

## Server Actions are public endpoints

### How the attacker exploits it
Next.js Server Actions compile into regular POST endpoints under the hood. Anyone can call them directly with `curl` — no browser, no UI, no click required. AI assistants frequently generate Server Actions that implicitly assume "only my UI calls this," which means the generated code skips input validation, authentication, and authorization because "the form already checks that."

```typescript
// BAD: no auth check, no input validation
'use server';
export async function deleteItem(id: string) {
  await db.items.delete({ where: { id } });
}
```
Anyone who inspects the client bundle or the network tab can find the action's endpoint and call it directly with an arbitrary `id`, deleting any item in the database regardless of who owns it — and regardless of whether the caller is even logged in.

### Where to look in the code
- Every file with `'use server'` at the top (or exported functions from a file marked that way).
- Check whether the top of the function body does all three of: parse/validate the input, check the session, and filter the operation by ownership.
- Functions that take an `id` (or any identifier) directly as a typed parameter with no runtime schema behind it.

### How to reproduce
Find the action's generated endpoint (inspect the Next.js RSC payload / network request the form triggers), then replay it directly with `curl`, passing an arbitrary id and no session cookie (or someone else's session cookie). If the delete/update succeeds, the action has no real protection.

### Fix
```typescript
// GOOD: validates input, authenticates, and authorizes
'use server';
export async function deleteItem(input: unknown) {
  const parsed = schema.safeParse(input);
  if (!parsed.success) return { error: 'Invalid input' };

  const session = await auth();
  if (!session?.user) redirect('/login');

  // Authorize: verify ownership, not just login
  await db.items.deleteMany({
    where: { id: parsed.data.id, userId: session.user.id }
  });
}
```
Every Server Action needs three things at the top, in this order:
1. **Input validation** — a runtime schema (Zod or similar), not a TypeScript type.
2. **Authentication** — verify the user is logged in.
3. **Authorization** — verify the user owns (or is otherwise entitled to) the resource being acted on.

---

## API route handlers (`app/api/`)

### How the attacker exploits it
The same reasoning applies to `app/api/` route handlers: every route handler is a public HTTP endpoint reachable by anyone who knows or guesses the path, independent of any UI that happens to call it.

### Where to look in the code
- Files under `app/api/**/route.ts` (or the equivalent in whatever router/framework is in use).
- Whether the handler authenticates and authorizes at the top before touching the database, or defers to "middleware already handled this" (see the Next.js middleware caveat in `04-authentication-session.md`).

### How to reproduce
Call the route handler directly with `curl`, without a session, and with a session belonging to a different user, targeting a resource owned by someone else. Any response that isn't a 401/403/404 for the wrong-owner case is a bug.

### Fix
Authenticate and authorize at the top of every handler — same three-item checklist as Server Actions: validate input, authenticate, authorize by ownership.

---

## Data leakage to Client Components

### How the attacker exploits it
Passing an entire database row/object down into a Client Component means every field on that object ends up serialized into the page's data and is inspectable in the browser (React DevTools, the page source, the network payload) — even fields never rendered on screen. This can leak hashed passwords, internal IDs, admin flags, or other users' data-adjacent fields that were fetched incidentally (e.g., via a join).

```typescript
// BAD: leaks all fields to the client
const user = await db.users.findUnique({ where: { id } });
return <UserProfile user={user} />;
```

### Where to look in the code
- Server Components / data-loading functions that fetch a full row (`findUnique`, `findFirst` with no `select`) and pass the whole object as a prop into a `'use client'` component.
- Data access modules that don't have `import 'server-only'` at the top, meaning nothing stops them from being imported directly into a Client Component by mistake.

### How to reproduce
Inspect the serialized props/payload sent to the client (React DevTools "Components" tab, or the RSC payload in the network tab) for a page that renders user data. Look for fields beyond what's visibly displayed — password hashes, internal role flags, other users' emails from a join.

### Fix
```typescript
// GOOD: select only needed fields
const user = await db.users.findUnique({
  where: { id },
  select: { name: true, avatarUrl: true }
});
return <UserProfile user={user} />;
```
- Select only the fields the client actually needs — never pass a full database object into a Client Component.
- Add `import 'server-only'` at the top of data access modules to prevent them from being accidentally imported into Client Components at all (the build fails instead of silently leaking).
