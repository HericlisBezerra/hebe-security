# Access Control / IDOR (Insecure Direct Object Reference)

**The most exploited vulnerability class in the real world.** The system trusts an identifier coming from the client (path, query string, or body) without checking whether the currently authenticated user is actually allowed to access the resource that ID points to.

Authorization is not the same thing as authentication. A route can correctly verify *who* the user is (valid token, valid session) and still be completely open to IDOR, because "is this a logged-in user?" and "may *this* user act on *this* resource?" are two separate checks — and it's the second one that gets skipped.

## Core IDOR

### How the attacker exploits it
```
GET  /api/posts/123        ← I am user 42, post 123 belongs to user 99
PUT  /api/orders/555       ← I modify an order that isn't mine
GET  /api/users/1/invoices ← I swap the 1 for my own ID, then for everyone else's
DELETE /api/comments/888   ← I delete someone else's comment
GET /api/posts/123/edit    ← user 42 requests an edit page for a post they don't own
```
The attacker simply increments/decrements a sequential numeric ID, or reuses a UUID they observed elsewhere (in a URL, an API response, a shared link), and tests whether the backend returns or mutates data belonging to another account. No special tooling required — this is often found by hand within minutes of poking at an app.

### Where to look in the code
- Handlers that receive an `id` from path/query/body and do a direct `find(id)` / `findUnique(id)` **without** an accompanying filter on `owner_id`, `user_id`, or `tenant_id`.
- Any query that looks up a resource strictly by primary key, with the ownership check (if it exists at all) happening as a separate `if` statement *after* the data has already been fetched — this pattern is easy to accidentally skip on one code path out of many.
- Frontend code that "only shows the user's own items" (e.g., a dropdown pre-filtered client-side) while the backend endpoint underneath accepts and serves any ID — the client never restricts what the server will do.
- Multi-tenant apps: any query missing a `WHERE tenant_id = ?` clause alongside the primary-key lookup.

### How to reproduce
1. Authenticate as User A, capture a valid auth token/session.
2. Find or guess a resource ID belonging to User B (sequential ID enumeration, or a UUID leaked in another response/URL).
3. Call the endpoint using User A's token but User B's resource ID.
4. If the response returns User B's data, or the mutation succeeds against User B's resource → confirmed IDOR.

Minimal reproduction as a one-liner:
```bash
# local or disposable staging, two test users
curl -s http://localhost:3000/api/posts/123 -H "Authorization: Bearer $TEST_USER_A_TOKEN"
# IDOR only if post 123 belongs to test user B, is not meant to be readable by A, and no other rule (sharing, public flag) grants it
```

### Fix
Every read and write must filter by ownership **inside the query itself**, not as an after-the-fact check on already-fetched data. Return **404** (not 403) for a resource that isn't the caller's — a 403 confirms the resource exists at all, which is itself information leakage; 404 reveals nothing about whether the ID is valid, deleted, or someone else's. In a review, a 403-vs-404 difference is hardening unless knowing that the ID exists is itself sensitive here (e.g. reveals a customer or a private record).

Generic pattern:
```
resource = find(where: { id, ownerId: session.userId })
if (!resource) → 404
```

Concrete pattern (Prisma):
```ts
const post = await prisma.post.findFirst({
  where: { id: postId, authorId: session.userId }
})
if (!post) return notFound() // 404, never 403 — don't reveal existence
```

In multi-tenant systems, filter by `tenant_id` in **every single query** that touches tenant-scoped data — consider a central guard/middleware that injects the tenant filter automatically so no individual query can forget it, rather than relying on every handler remembering to add it by hand.

Never trust the frontend to do this filtering for you: every authorization decision — every ownership check, every state-transition rule — must be re-verified server-side, even if the client already enforces it. The client is not a trust boundary; the server is the only one.
