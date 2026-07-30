# Stack Adapters — technology-specific signatures

Load only the section(s) for the stack detected in Phase 1. Each adapter translates the concepts from the numbered category files into that technology's actual code signature: where the vulnerability shows up, and what the idiomatic fix looks like.

---

## Node.js / TypeScript (Express, Fastify, NestJS)

- **IDOR:** `Model.findById(req.params.id)` with no owner filter. Fix: include `where: { id, userId: req.user.id }`.
- **Validation:** use **Zod** or **Valibot** — a single schema shared front+back. No schema in the handler is a red flag.
- **SQLi:** Prisma/Drizzle/Knex parametrize. Risk: `$queryRawUnsafe`, `knex.raw` with a template string, `sequelize.query` with interpolation.
- **Race conditions:** `prisma.$transaction(fn, { isolationLevel: 'Serializable' })`; or an atomic `UPDATE ... WHERE balance >= ?`.
- **Established auth:** Better-Auth, Auth.js/NextAuth, Lucia, Clerk, Passport. Custom crypto = review thoroughly.
- **Rate limiting:** `express-rate-limit`, `@fastify/rate-limit`, Upstash Ratelimit (edge).
- **Mass assignment:** `prisma.user.update({ data: req.body })` used blindly. Fix: explicit pick of allowed fields.
- **Headers:** `helmet()` in Express covers CSP/HSTS/frame-options.
- **Dependencies:** `npm audit` / `pnpm audit`.

## Next.js (App Router / Pages Router)

- **Server Actions / Route Handlers:** each action is a public endpoint — validate auth + ownership INSIDE it, never trust that only the UI calls it. `"use server"` is not a security boundary.
- **`NEXT_PUBLIC_*`:** any env var with this prefix ships to the client bundle. A secret placed there is leaked. Audit for this.
- **Middleware:** an auth check in `middleware.ts` protects navigation but does NOT replace a per-resource check inside the handlers.
- **Server-only API keys:** confirm they are never imported into a client component.
- **RSC:** sensitive data fetched in a Server Component must not leak as a prop passed down into a Client Component.

## Python (Django, Flask, FastAPI)

- **Django:** IDOR via `Model.objects.get(pk=id)` without `filter(owner=request.user)`. The ORM protects against SQLi (risk: `.raw()`, `.extra()`, cursor with `%` interpolation). Mass assignment via a `ModelForm` without explicit `fields`. Is CSRF middleware active? Are `SECURE_*` settings configured (HSTS, SSL redirect)? Is `DEBUG=False` in production?
- **Flask:** more "hand-rolled" → more attack surface. Validate with Pydantic/marshmallow. Rate limiting: `Flask-Limiter`. SQLAlchemy parametrizes (risk: `text()` with an f-string). Session: `SECRET_KEY` strong and kept out of the code.
- **FastAPI:** Pydantic validates input by default (good) — but use `response_model` to avoid leaking extra fields. `Depends` for auth/authz; confirm the dependency actually checks ownership, not just identity.
- **Hashing:** `argon2-cffi` or `passlib[bcrypt]`. Never `hashlib.md5/sha256` for passwords.
- **Dependencies:** `pip-audit`.

## Ruby on Rails

- **IDOR:** `Model.find(params[:id])` with no scope. Fix: `current_user.posts.find(params[:id])`.
- **Mass assignment:** strong params — `params.require(:x).permit(:a,:b)`. `permit!` is dangerous.
- **SQLi:** ActiveRecord parametrizes (risk: `where("name = '#{x}'")` — interpolation). Use `where("name = ?", x)`.
- **Auth:** Devise (established). Custom = review.
- **Race conditions:** `with_lock`, `SELECT FOR UPDATE`, optimistic locking (`lock_version`).
- **General security:** run **Brakeman** (Rails-native SAST, excellent). `bundle audit` for dependencies.
- **Credentials:** `config/credentials.yml.enc` + master key kept out of the repo.

## PHP / Laravel

- **IDOR:** `Model::find($id)` without `->where('user_id', auth()->id())`. Use Policies/Gates for authorization.
- **Mass assignment:** `$fillable` allowlist vs `$guarded`. `Model::create($request->all())` with no fillable defined is a risk.
- **SQLi:** Eloquent/query builder parametrize (risk: `DB::raw`, `whereRaw` with string concatenation).
- **Validation:** Form Requests / `$request->validate()`.
- **XSS:** Blade `{{ }}` escapes; `{!! !!}` does NOT — audit every use.
- **Dependencies:** `composer audit`.

## Go (Gin, Echo, net/http)

- **SQLi:** `database/sql` parametrizes with `?`/`$1` placeholders (risk: `fmt.Sprintf` used to build a query). sqlc/GORM help enforce this.
- **IDOR:** a query missing `WHERE user_id = ?`.
- **Race conditions:** a transaction with `SELECT ... FOR UPDATE`; or `sync` primitives at the right level (but prefer a database-level lock for persisted state).
- **Validation:** `go-playground/validator` struct tags.
- **Dependencies:** `govulncheck`.

## Supabase (any frontend)

- **RLS is the central piece.** Every table must have RLS enabled. Explicit policy per operation. `USING (true)` = wide open.
- **Test with the anon key** — if it returns another user's data, RLS is broken. Never ship `service_role` to the client.
- **Native auth:** use `supabase.auth` — don't reinvent it. Use `auth.uid()` inside policies.
- **Storage:** buckets need their own policies; a public bucket means exposed files.
- **Edge Functions:** validate auth inside the function; secrets live in `supabase secrets`, never in the code.
- **Classic trap:** "a Supabase app is a ticking time bomb" — not because of the tool, but because of misconfigured RLS plus an exposed database. The problem is the developer, not Supabase.

## Firebase

- **Security Rules** are Firebase's equivalent of RLS. Default deny, then authorize explicitly. `allow read, write: if true` = open to the entire world.
- Test with the Rules emulator. The client config (`apiKey`) is public by design — security comes from the Rules, not from hiding the key.

## Convex

- **Public `query`/`mutation` functions are public endpoints**, exactly like a REST route — anyone who can call the deployment can call them. Every public query/mutation that touches user data must call `ctx.auth.getUserIdentity()` and check it's non-null before doing anything.
- **Ownership check is still required:** authenticating the caller (`getUserIdentity`) only proves *who* they are — the function body still must verify the caller owns/may access the specific document being read or mutated, the same as any other backend (don't just check "is logged in", check "is logged in **and** owns this row").
- **Use `internalQuery` / `internalMutation` / `internalAction`** for any function that should only ever be called from other server-side Convex functions (e.g. from a scheduled function or another mutation), never directly from a client. If a function only exists to be called internally but is declared as a public `query`/`mutation`, it's reachable by anyone.
- **Schema validation:** define argument validators (`v.string()`, `v.id("table")`, etc.) on every function — an unvalidated argument object is the mass-assignment equivalent for Convex.

## React Native / Expo

- **`EXPO_PUBLIC_*` env vars and `react-native-config` values ship inside the compiled app bundle** — anyone who downloads the app (from the App Store, Play Store, or an APK) can extract and read them. Never put a secret, private API key, or signing secret behind these — they are exactly as public as a `NEXT_PUBLIC_*` variable, just distributed via an app binary instead of a webpage.
- **`AsyncStorage` vs `SecureStore`:** `AsyncStorage` is unencrypted plaintext storage on-device — do not store auth tokens, refresh tokens, or any credential there. Use `expo-secure-store` (backed by Keychain on iOS / Keystore on Android) for anything sensitive.
- **Deep links:** a deep link handler that trusts its parameters without validation can be used to trigger unintended app state (e.g. `myapp://reset-password?token=...` replayed from a malicious link, or a deep link that navigates straight into an authenticated screen bypassing an auth check). Validate and re-authorize inside the deep link handler exactly as you would a normal route — don't assume only your own app will construct these URLs.

---

## If the stack isn't listed here

Apply the **concepts** from the numbered category files (they are universal) and look for the idiomatic signature of that framework: how does it build queries (does it parametrize?), how does it validate input, how does it do auth, how does it isolate tenants. The attack is the same; only the fix's syntax changes.
