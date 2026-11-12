# Injection (SQL, XSS, SSRF, Command, Template)

Stack-agnostic offensive reference. For each subtopic: how the attacker exploits it, where to look in the code, how to reproduce, how to fix. Combine with `stack-adapters.md` for the exact signature of the detected stack.

---

## SQL Injection

### How the attacker exploits it
A modern ORM with parameterization protects you by default. The risk is `raw()` / `$queryRawUnsafe` / string concatenation. The attacker sends input like `' OR 1=1 --` or a stacked statement into any field that ends up inside a query string, and the database executes it as code instead of data.

### Where to look in the code
- Queries built with `+` / string concatenation.
- f-strings or template interpolation with user input inside SQL.
- `$queryRawUnsafe`, `$executeRawUnsafe` (Prisma) or equivalent raw-SQL escape hatches in any ORM.
- Anywhere user input reaches a query without going through a parameter/placeholder.

### How to reproduce
Locally or against a disposable database with fictitious data, send non-destructive probes (`'`, `' OR 1=1 --`, a boolean pair like `' AND 1=1 --` vs `' AND 1=2 --`) in a field that reaches a query. Never send `DROP`, `DELETE` or stacked writes. A SQL syntax error alone only shows the quote reached the parser; confirmation needs the injected clause to change the result (extra/other rows, boolean difference) — and the source trace to the unparameterized query.

### Fix
Always use parameterized queries or ORM methods. Never concatenate user input into SQL strings.

```typescript
// BAD: SQL injection via string concatenation
const result = await db.query(`SELECT * FROM users WHERE id = '${userId}'`);

// GOOD: parameterized query
const result = await db.query('SELECT * FROM users WHERE id = $1', [userId]);
```

**Never use `$queryRawUnsafe` or `$executeRawUnsafe` with user-supplied input.** These bypass the ORM's parameterization entirely.

```typescript
// BAD: raw SQL with user input
const results = await prisma.$queryRawUnsafe(
  `SELECT * FROM users WHERE name = '${name}'`
);

// GOOD: use the safe raw query with parameters
const results = await prisma.$queryRaw`
  SELECT * FROM users WHERE name = ${name}
`;
```

---

## ORM operator injection (Prisma and similar)

### How the attacker exploits it
Even with an ORM, injection is possible at the *filter-object* level, not just via raw SQL. `findFirst` and similar methods are vulnerable to operator injection if unvalidated objects are passed as filter values. An attacker can send `{ "email": { "contains": "" } }` as the request body and match **all records**, because the ORM interprets `contains` as a query operator rather than a literal value.

### Where to look in the code
- Any handler that passes `req.body` (or an unvalidated object) directly as the `where` clause to `findFirst`/`findMany`/`update`/`delete`.
- Absence of a Zod/Valibot/Pydantic schema between the request body and the ORM call.

### How to reproduce
POST a filter object like `{ "email": { "contains": "" } }`, `{ "id": { "not": 0 } }`, or `{ "OR": [...] }` to an endpoint that forwards the body straight into a `where` clause. If it returns records it shouldn't (e.g. all users instead of one), the operator injection succeeded.

### Fix
**Validate input types with Zod (or equivalent) before passing to the ORM.**

```typescript
// BAD: raw request body passed directly to Prisma
const user = await prisma.user.findFirst({ where: req.body });

// GOOD: validate with Zod first
const schema = z.object({ email: z.string().email() });
const parsed = schema.parse(req.body);
const user = await prisma.user.findFirst({ where: { email: parsed.email } });
```

---

## XSS (Cross-Site Scripting)

### How the attacker exploits it
Modern frameworks escape output by default, so the attacker looks for the escape hatches: React's raw-HTML prop (`dangerouslySetInnerHTML`), Vue's `v-html`, direct `innerHTML` assignment, unsanitized Markdown/HTML rendering of user content, or server-side rendering that concatenates strings directly into HTML. A payload like `<script>alert(1)</script>` or `<img src=x onerror=alert(1)>` gets stored and later executed in another user's browser — session theft, action-on-behalf-of-victim, credential phishing.

### Where to look in the code
- React's `dangerouslySetInnerHTML` prop, Vue's `v-html`, direct `innerHTML` assignment.
- Markdown/HTML render pipelines without an allowlist sanitizer (`remark`/`marked` without `rehype-sanitize`/`DOMPurify`).
- SSR templates joining strings with user data instead of using the framework's escaping.

### How to reproduce
Submit `<script>alert(1)</script>` or `<img src=x onerror=alert(1)>` into any field that is later rendered (post body, bio, comment, display name). If the script executes instead of rendering as literal text, it's vulnerable.

### Fix
Sanitize with **DOMPurify** (client) or `rehype-sanitize` (server/Markdown pipelines) whenever rendering user-supplied HTML. Add a **Content-Security-Policy** header as a last line of defense:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; img-src 'self' data: https:;
```

---

## SSRF (Server-Side Request Forgery)

### How the attacker exploits it
The backend fetches a URL controlled by the user, and the attacker points it at internal infrastructure — cloud metadata endpoints (`http://169.254.169.254/`), internal services, or localhost-only admin ports. A common entry point in vibe-coded apps: a profile field that accepts an external image URL. Even without a proxy, this doubles as an IP tracker (the victim's/server's IP hits the attacker's endpoint when the image loads); with a server-side proxy/fetch, it becomes real SSRF against internal networks.

### Where to look in the code
- Any handler that does a server-side fetch of a user-supplied URL (image proxy, link preview, webhook test, "import from URL" feature).
- Profile/avatar fields that store and later re-fetch an arbitrary external URL.

### How to reproduce
Submit an internal/link-local address (`http://169.254.169.254/latest/meta-data/`, `http://localhost:PORT/admin`) as the URL value and see if the server fetches it and returns/leaks the response.

### Fix
Do not fetch arbitrary user-supplied URLs from the backend. If unavoidable:
- Allowlist of domains.
- Block private/link-local IP ranges (resolve DNS and check the resulting IP, not just the hostname string).
- Short timeout, small max response size.
- Prefer re-hosting the resource: fetch once server-side and store/serve your own copy rather than proxying live requests.

---

## Command Injection / Template Injection (SSTI)

### How the attacker exploits it
Shell-invocation APIs that include user input let the attacker break out of the intended argument and run arbitrary shell commands (RCE). Similarly, a template engine that renders user-controlled input as a template (instead of as data) allows Server-Side Template Injection — the attacker's payload is evaluated as template syntax, often leading to RCE.

### Where to look in the code
- Any shell-invoking call (Node's shell-mode process spawning, Python's `os.system`/`subprocess` with `shell=True`, PHP's shell functions) built with string concatenation of user input.
- JavaScript's dynamic code-evaluation builtin, or any language's equivalent, used anywhere near user input.
- Template engines (Jinja2, Handlebars, EJS, etc.) rendering a string that came from user input as a *template* rather than as a *value*.

### How to reproduce
For command injection: try shell metacharacters (`; ls`, backtick-wrapped commands, `$(id)`) in any field that reaches a shell call. For SSTI: try template syntax specific to the engine (e.g. `{{7*7}}`, `${7*7}`) and see if it evaluates to `49` instead of being rendered literally.

### Fix
Never pass user input to a shell. If a subprocess is unavoidable, use APIs that separate arguments from the command (array-form invocation, not string-form) so there's no shell parsing step at all. Never run dynamic code-evaluation on untrusted strings. For templating, always render user input as *data* passed into a template, never as the template source itself.

---

## Input Validation (supporting control for all injection classes)

Validate all external input at system boundaries using a runtime schema validator (Zod, Yup, Joi, Valibot, Pydantic, etc.):

- API route handlers
- Server Actions
- Webhook handlers
- Form submissions
- URL parameters and query strings

Don't rely on TypeScript types alone — they're compile-time only and don't exist at runtime. An attacker sending a malformed request bypasses all TypeScript checks.

```typescript
// TypeScript type provides NO runtime protection
type CreateUserInput = { name: string; email: string };

// Zod schema provides ACTUAL runtime validation
const CreateUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
});
```
