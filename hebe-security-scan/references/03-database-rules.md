# Database and Serverless Rules (RLS, Firebase Rules, Convex)

This is the **#1 source of critical vulnerabilities in vibe-coded apps.** AI assistants routinely generate database schemas and serverless backends without proper access control, leaving entire tables — or entire collections — exposed to anyone with the public/anon client key. A table without a rule, and a table with a *wrong* rule, look identical from the outside until someone actually tests them.

---

## Supabase Row-Level Security (RLS)

### Enable RLS on Every Table

#### How the attacker exploits it
Tables created with SQL (SQL Editor or migrations) have RLS **disabled by default**. With RLS off, access is governed only by ordinary GRANTs. On many Supabase projects a new `public` table starts with full privileges granted to `anon` and `authenticated`, so in an exposed schema it is readable and writable by anyone holding the `anon` key — and the `anon` key is, by design, public (it ships in the client bundle). Confirm the grants and whether the schema is exposed through the Data API before calling it open. An attacker doesn't even need to find a bug in a policy; they just need to find a table where RLS was never turned on at all, which happens constantly when new tables are added after the initial security pass and nobody remembers to re-run the checklist.

#### Where to look in the code
Check every table in the `public` schema (and any other schema exposed via PostgREST) for RLS status:
```sql
SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
```
A table where `rowsecurity` is `false` is open to the extent of its grants; check them (this counts grants to `PUBLIC` and inherited roles):
```sql
SELECT has_table_privilege('anon', 'public.<table>', 'SELECT') AS anon_select,
       has_table_privilege('anon', 'public.<table>', 'INSERT,UPDATE,DELETE') AS anon_write,
       has_table_privilege('authenticated', 'public.<table>', 'SELECT') AS auth_select;
```
Migration scripts should be scanned for tables created without a corresponding `ENABLE ROW LEVEL SECURITY` statement.

A defensive migration to catch every missed table:
```sql
DO $$ DECLARE r RECORD;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', r.tablename);
  END LOOP;
END $$;
```

#### How to reproduce
**Test with the `anon` key, never with `service_role`.** This is the single most important testing discipline for RLS: the `service_role` key bypasses RLS entirely, so testing with it will always look secure regardless of the actual policy configuration — it proves nothing. Reproduce with the public client exactly as an attacker would use it, against a local stack (`supabase start` with the migrations applied) and fictitious test users — never the published project:
```bash
curl "http://127.0.0.1:54321/rest/v1/documents?select=*" \
  -H "apikey: <local_anon_key>" \
  -H "Authorization: Bearer <local_anon_key_or_test_user_jwt>"
```
If this returns rows belonging to other users (or returns rows at all when it shouldn't), RLS is broken — either missing entirely or misconfigured.

#### Fix
Enable RLS on **every** table, with no exceptions, then author explicit per-operation policies (select/insert/update/delete) — never leave a table exposed via the REST API without RLS active.

---

### Dangerous RLS Policies

#### How the attacker exploits it
A policy that technically "exists" can still grant blanket access if its condition is too permissive. The two most common mistakes:
```sql
-- BAD: any logged-in user can read all rows
CREATE POLICY "Users can view data" ON public.documents
  FOR SELECT TO authenticated USING (true);

-- BAD: any logged-in user can read all rows
CREATE POLICY "Users can view data" ON public.documents
  FOR SELECT TO authenticated USING (auth.uid() IS NOT NULL);
```
Both of these check only "is someone logged in?" — not "does this row belong to them?" Any authenticated user (including an attacker who just signed up for a free account) can read or modify every row in the table.

#### Where to look in the code
Grep migrations and policy definitions for `USING (true)` and `USING (auth.uid() IS NOT NULL)` on `SELECT`, `UPDATE`, or `DELETE` policies — these are almost never correct outside of genuinely public data (e.g. a public blog post table).

#### How to reproduce
Same as above: query the table with the `anon` key / a low-privilege user's JWT and confirm whether rows belonging to *other* users are returned.

#### Fix
Always scope to the row owner:
```sql
-- GOOD: users can only read their own rows
CREATE POLICY "Users can view own data" ON public.documents
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
```
As a general audit heuristic: any policy `USING` clause that references only `auth.uid()`'s existence, and never compares it against a column on the row, should be treated as a candidate to check: it is a finding when the table holds per-user or per-tenant data and a test user can read or write another user's rows; on genuinely shared data it is not.

---

### Write policies that let ownership change (WITH CHECK)

#### How the attacker exploits it
For `UPDATE` (and `FOR ALL`), PostgreSQL checks the existing row against `USING` and the new row against `WITH CHECK`; when `WITH CHECK` is omitted, the `USING` expression is reused as the check. So `FOR UPDATE USING (auth.uid() = user_id)` alone already blocks changing `user_id` to someone else. `FOR INSERT` accepts only `WITH CHECK` (a `USING` there is a syntax error). The real risks are:
```sql
-- BAD: WITH CHECK looser than USING — owner can hand the row to anyone
CREATE POLICY "Users can update tasks" ON public.tasks
  FOR UPDATE TO authenticated
  USING ((SELECT auth.uid()) = user_id)
  WITH CHECK (true);

-- BAD: INSERT check that never compares the owner column
CREATE POLICY "Users can create tasks" ON public.tasks
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() IS NOT NULL);
```
Also look at policies whose `USING` does not constrain the owner/tenant column at all, and at a second permissive policy on the same command — permissive policies combine with OR, so the loosest one wins.

#### Where to look in the code
- `FOR UPDATE`/`FOR ALL` policies whose `WITH CHECK` is present and weaker than `USING` (e.g. `true`, only `auth.uid() IS NOT NULL`, or a different column).
- `FOR INSERT` policies whose `WITH CHECK` does not compare `auth.uid()` (or the tenant) with the owner column.
- Several permissive policies for the same table and command.

#### How to reproduce
On a local or disposable database with two test users, as user A attempt to `UPDATE` a row A owns setting its owner column to user B's ID, or `INSERT` a row with `user_id` set to B's ID. If it succeeds, the write check is too loose.

#### Fix
```sql
-- GOOD: explicit and equal on both sides
CREATE POLICY "Users can update tasks" ON public.tasks
  FOR UPDATE TO authenticated
  USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can create tasks" ON public.tasks
  FOR INSERT TO authenticated
  WITH CHECK ((SELECT auth.uid()) = user_id);
```

---

### Sensitive Fields on User-Accessible Tables (Mass Assignment via RLS)

#### How the attacker exploits it
If a `profiles` table lets users `UPDATE` their own row, and the policy only checks ownership (not *which columns* are being changed), a user can set `is_admin = true`, `credits = 99999`, or `subscription_tier = 'enterprise'` on their own row — granting themselves privileges or value they were never supposed to have. This is the RLS-flavored version of classic mass assignment, and it is one of the most damaging and most overlooked findings in Supabase apps, because the policy "looks correct" (it does check ownership) while still being fully exploitable.

#### Where to look in the code
Any table with columns like `is_admin`, `role`, `credits`, `balance`, `subscription_tier`, `verified` that is covered by a broad `FOR UPDATE ... USING (auth.uid() = user_id)` policy without column-level restriction.

#### How to reproduce
As a normal authenticated user, attempt `UPDATE profiles SET is_admin = true WHERE id = auth.uid()` (via the REST API with the anon key + user JWT). If it succeeds, the sensitive field is attacker-controllable.

#### Fix
- **Option A:** Move sensitive fields to a `private` schema table not exposed via PostgREST. Access them only through `SECURITY DEFINER` functions that enforce the actual business rules for changing them.
- **Option B:** Use column-level privileges to allow updates only to safe fields:
  ```sql
  REVOKE UPDATE ON profiles FROM authenticated;
  GRANT UPDATE (display_name, avatar_url) ON profiles TO authenticated;
  ```

---

### Forgotten Related Tables

#### How the attacker exploits it
Junction tables, audit logs, and metadata tables are frequently created as an afterthought to support a feature, and often lack RLS even when the "main" table in the same feature has it correctly configured. Every table exposed via the REST API needs its own policies — RLS does not cascade from a parent table to a related one just because they're joined in application code.

#### Where to look in the code
Any table referenced by a foreign key from a properly-secured table, but not itself checked for RLS status. Re-run the "list all tables and their `rowsecurity` flag" query (above) after every schema change, not just at initial setup.

#### How to reproduce
Query the related/junction table directly (not through the main table's join) with the anon key and check whether rows are returned that shouldn't be visible to the caller.

#### Fix
Audit every table in the schema, not just the ones a feature obviously touches. If a table has RLS enabled but no policies defined, it blocks all access — which is a safe default, but can cause subtle functional bugs (silently empty results) that should be caught in testing, not shipped as a mystery.

---

### SECURITY DEFINER Functions

#### How the attacker exploits it
`SECURITY DEFINER` functions run with the privileges of the function's owner, not the caller. Whether that bypasses RLS depends on the owner: superusers and `BYPASSRLS` roles always bypass it, and a table owner bypasses it unless the table has `FORCE ROW LEVEL SECURITY`. On Supabase, functions created in the Dashboard or by migrations are owned by `postgres`, which bypasses RLS. `EXECUTE` is granted to `PUBLIC` by default, so a definer function in an exposed schema (e.g. `public`) is callable through `rpc()` by `anon` unless `EXECUTE` is revoked from both `PUBLIC` and `anon` (Supabase also grants it to `anon`/`authenticated` explicitly through default privileges) — regardless of what RLS policies exist on the tables it touches internally.

#### Where to look in the code
Grep migrations for `SECURITY DEFINER` and check: (1) what schema the function lives in, (2) who owns it and whether the tables it touches use `FORCE ROW LEVEL SECURITY`, (3) whether `EXECUTE` was revoked from `PUBLIC` **and** `anon` (and `authenticated` if not intended) — confirm with `has_function_privilege('anon', 'public.f(argtypes)', 'EXECUTE')`, (4) whether it validates its inputs and the caller, (5) whether `search_path` is pinned.

#### How to reproduce
Call the function via `rpc()` using the anon key and see whether it returns or mutates data that RLS should have blocked.

#### Fix
- Keep `SECURITY DEFINER` functions in a `private` schema, not `public`, so they aren't auto-exposed via the REST API.
- If it must stay callable from a client, revoke what is not intended: `REVOKE EXECUTE ON FUNCTION public.f(argtypes) FROM PUBLIC, anon;` (and `authenticated` when only the server calls it).
- Set `SET search_path = ''` on the function to prevent search-path hijacking (an attacker-controlled schema earlier in the path could otherwise shadow a table/function the definer-privileged function relies on).
- Validate all inputs inside the function body — it is your last line of defense once RLS has been bypassed by design.

---

### Storage Buckets

#### How the attacker exploits it
Storage buckets are a separate permission surface from database tables and are easy to forget. With no policy on `storage.objects`, Storage denies uploads and other operations (safe, but often "fixed" with an over-broad policy). A **public** bucket lets anyone with the URL read (download) its files without any policy, but uploads, deletes, moves and copies still require policies. The real risks are a policy that does not scope by bucket and owner folder (any authenticated user can read, overwrite or delete other users' files) and sensitive files placed in a public bucket.

#### Where to look in the code
Check `storage.objects` policies for each bucket used by the app: a policy that omits `bucket_id` or the owner-folder check allows cross-user file access. Check which buckets are public and whether they hold anything that is not meant for anyone with the link.

#### How to reproduce
As User A, attempt to read, overwrite, or delete a file path known to belong to User B (e.g. `avatars/<user_b_uuid>/photo.jpg`) using the anon key + User A's JWT.

#### Fix
Scope uploads (and reads/deletes) to the user's own UID folder:
```sql
CREATE POLICY "Users upload to own folder"
  ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'avatars'
    AND (storage.foldername(name))[1] = (SELECT auth.uid())::TEXT
  );
```

---

## Firebase Security Rules

### Default Rules Are Dangerous

#### How the attacker exploits it
Firebase's permissive default/example rules are frequently left in place or copy-pasted by AI assistants trying to "make it work," and they grant far more access than intended:
```
// BAD: world-readable and writable
allow read, write: if true;

// BAD: any logged-in user can access everything
allow read, write: if request.auth != null;
```
The first allows literally anyone, authenticated or not, to read and write the entire database. The second is only marginally better — any user who has signed up (which is usually free and instant) gets full access to every other user's data.

#### Where to look in the code
`firestore.rules` / `storage.rules` — search for `if true`, `if request.auth != null` used as the *entire* condition on read/write without any further ownership check.

#### How to reproduce
Using the Firebase emulator or the actual client SDK authenticated as a low-privilege test user, attempt to read/write a document that belongs to a different `userId`.

#### Fix
Always validate ownership explicitly:
```
allow read, write: if request.auth.uid == userId;
```

---

### Field-Level Protection

#### How the attacker exploits it
Even with a correct ownership check on the document, without restricting *which fields* a user is allowed to modify, they can include arbitrary extra fields in their write — e.g. setting `isAdmin: true` or `credits: 99999` on their own document during an otherwise-legitimate profile update.

#### Where to look in the code
Any `allow update` rule that checks `request.auth.uid == userId` but doesn't constrain `request.resource.data` against the set of fields that should be editable.

#### How to reproduce
As an authenticated user, submit an update to your own document that includes a privileged field (`isAdmin`, `role`, `credits`) alongside a legitimate field, and check whether it's accepted.

#### Fix
Restrict which fields can be changed on `UPDATE` using `affectedKeys().hasOnly(...)`:
```
// GOOD: restrict modifiable fields on UPDATE
allow update: if request.auth.uid == userId
  && request.resource.data.diff(resource.data)
     .affectedKeys()
     .hasOnly(['displayName', 'avatarUrl']);
```

---

### Subcollection Trap

#### How the attacker exploits it
Firestore subcollections are **NOT** automatically secured by the parent document's rules. A developer (or AI assistant) who writes a solid rule for `/users/{userId}` and assumes it also protects `/users/{userId}/privateNotes/{noteId}` is wrong — the subcollection is a completely separate rule target and, if unaddressed, may default to fully open or fully closed in ways that surprise the author. AI assistants frequently miss this because it isn't visually obvious from the parent rule's structure.

#### Where to look in the code
Every subcollection path referenced in application code needs its own explicit `match` block in `firestore.rules`. Search the rules file for every collection the client code reads/writes and confirm each nesting level has its own rule.

#### How to reproduce
Attempt to read/write a subcollection document directly (not through the parent) as a user who should not have access, and confirm whether the parent's ownership check was (incorrectly) assumed to apply.

#### Fix
Write an explicit `match` block for every subcollection, re-stating (or re-deriving) the same ownership check rather than relying on inheritance from the parent path.

---

### Data Validation

#### How the attacker exploits it
Without type and size validation in the rules themselves, a client can write malformed data (wrong types, oversized strings) directly to the database, since Firestore rules are the only server-side gate — there's no separate backend validating the shape of writes unless you add one.

#### Where to look in the code
`allow create`/`allow update` rules that check auth/ownership but never inspect `request.resource.data` field types or sizes.

#### How to reproduce
Submit a write with a wildly oversized string field or a wrong data type for a field (e.g. a number where a string is expected) and confirm it's accepted.

#### Fix
Validate data types and sizes on writes:
```
allow create: if request.resource.data.displayName is string
  && request.resource.data.displayName.size() <= 50;
```
Enforce server-derived timestamps rather than trusting client-supplied ones:
```
allow create: if request.resource.data.createdAt == request.time;
```

---

### Role Checks

#### How the attacker exploits it
If role/permission checks are implemented by reading a `role` field from a Firestore document (e.g. `/users/{uid}.role`), and that document is writable by the user (even indirectly, through a missed field-level restriction — see above), the "role check" is circular and can be self-escalated.

#### Fix
Use **custom claims** (`request.auth.token.role`) instead of querying a user document for role/permission checks. Custom claims are set via the Admin SDK server-side, cannot be tampered with by the client, and don't require an extra document read inside the rule.

---

### Cloud Storage Rules

#### How the attacker exploits it
Cloud Storage for Firebase has its own rules file, separate from Firestore rules, and is just as easy to leave under-protected. Without validating `contentType`, `size`, and path ownership, users can upload executable files disguised as something else, oversized files (storage cost / DoS), or write into another user's storage path.

#### Where to look in the code
`storage.rules` — check that every `allow write` validates `request.resource.contentType`, `request.resource.size`, and that the path segment matches `request.auth.uid`.

#### How to reproduce
Attempt to upload a file with a spoofed `contentType`, an oversized payload, or to a path under another user's UID, and confirm whether the rule rejects it.

#### Fix
Validate `contentType`, `size`, and path ownership on every storage write rule, mirroring the same per-user path scoping pattern used for Supabase storage buckets above.

---

## Convex

### Missing Auth Check in Public Functions

#### How the attacker exploits it
Every public `query` and `mutation` in Convex is directly callable by any client. If a function doesn't check `ctx.auth.getUserIdentity()`, it runs for unauthenticated callers exactly as it would for authenticated ones.

#### Where to look in the code
Every exported `query`/`mutation` — confirm each one calls `ctx.auth.getUserIdentity()` near the top and explicitly handles the `null`/unauthenticated case (rejecting or scoping the response), rather than proceeding straight to the data access.

#### Fix
Call `ctx.auth.getUserIdentity()` and handle the unauthenticated case in every public `query` and `mutation`.

### Ownership Not Verified

#### How the attacker exploits it
Checking that *someone* is authenticated is not the same as checking that the authenticated caller owns the specific document/resource being modified — this is the Convex expression of the general IDOR pattern. A mutation that verifies auth but then updates a record by ID without checking who owns it is exploitable exactly like an unprotected REST endpoint.

#### Fix
Mutations must verify ownership — checking auth is not enough. Verify the user owns the specific resource they're modifying before applying the change.

### Internal Functions Exposed as Public

#### How the attacker exploits it
Functions meant to be called only by other backend functions (internal business logic, privileged operations) are directly callable by any client if declared as `query`/`mutation`/`action` instead of their internal counterparts.

#### Fix
Functions only called internally must use `internalQuery` / `internalMutation` / `internalAction`, not `query` / `mutation` / `action`. Public functions are callable by anyone with network access to the deployment — treat that distinction as a hard security boundary, not a naming convention.
