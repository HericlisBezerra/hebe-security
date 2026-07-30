# Input Validation

## Server-side validation at every boundary

### How the attacker exploits it
If validation only runs on the frontend, an attacker calls the API directly — with `curl`, Postman, or a scripted client — and skips the frontend entirely. Whatever the frontend "wouldn't let you type" is fully reachable at the API layer. TypeScript types provide zero protection here: they're compile-time only and don't exist at runtime. An attacker sending a malformed request bypasses every TypeScript check with no effort, because the check never actually ran.

```typescript
// TypeScript type provides NO runtime protection
type CreateUserInput = { name: string; email: string };
```

### Where to look in the code
Validate all external input at every system boundary using a runtime schema validator (Zod, Valibot, Yup, Joi, dry-validation, Pydantic, etc.). The boundaries to check, specifically:
- API route handlers
- Server Actions
- Webhook handlers
- Form submissions
- URL parameters and query strings

Look for:
- Schemas that exist only in frontend form code, with nothing equivalent enforced server-side.
- Handlers that destructure `req.body` (or the Server Action input) directly into typed variables with no `.parse()`/`.safeParse()` call anywhere above.
- A TypeScript `type`/`interface` used as if it were a runtime guarantee.

### How to reproduce
Call the endpoint directly (bypassing the UI) with a payload that the frontend would have rejected — wrong types, missing required fields, extra unexpected fields, or an operator-injection object (see Mass Assignment / ORM notes below). If the backend accepts and processes it anyway, there is no real validation.

### Fix
```typescript
// Zod schema provides ACTUAL runtime validation
const CreateUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
});
```
Also watch the ORM layer itself — even with a modern ORM (Prisma, Drizzle, etc.), passing an unvalidated object straight through as a filter can enable operator injection:
```typescript
// BAD: raw request body passed directly to Prisma
const user = await prisma.user.findFirst({ where: req.body });
// An attacker can send { "email": { "contains": "" } } to match all records.

// GOOD: validate with Zod first
const schema = z.object({ email: z.string().email() });
const parsed = schema.parse(req.body);
const user = await prisma.user.findFirst({ where: { email: parsed.email } });
```

---

## Size limits on every field

### How the attacker exploits it
A field with no maximum length accepts an arbitrarily large payload. This pollutes the database, inflates storage cost, degrades query/index performance, and can be used as a straightforward denial-of-service vector — even on fields that look "harmless" like a name or title.

### Where to look in the code
- Validation schemas missing a `.max()` (or equivalent) on string fields.
- **The subtle trap:** a field that only accepts a URL on your own domain can still be attacked — an attacker appends an enormous query string to an otherwise-fixed URL. "The path is fixed so I don't need a length limit" is false; limit the total string length regardless.

### How to reproduce
Submit a field (name, title, comment, etc.) with 10,000+ characters and confirm whether the request succeeds. It should be rejected with a 400.

### Fix
Reference order-of-magnitude limits (adjust per field's real use):

| Field | Max characters |
|---|---|
| Name, short title | 100–200 |
| Slug | 100 |
| Bio, short description | 500 |
| Post/comment | 2,000–5,000 |
| Long article/lesson | 50,000 |
| URL | 2,048 (practical HTTP limit) |
| Email | 254 (RFC) |

Use a schema library (Zod, Valibot) as the single source of truth for limits, shared between frontend and backend where possible.

---

## File upload validation

### How the attacker exploits it
An upload endpoint that trusts the client-supplied filename extension or `Content-Type` header can be handed an executable disguised as an image (`shell.php` renamed to `shell.php.png`, or served with `Content-Type: image/png` regardless of actual content), an SVG containing an embedded script, a zip bomb, or an oversized file meant to exhaust storage/bandwidth.

### Where to look in the code
- Upload handlers that branch on the file extension or the `Content-Type` header sent by the client, without inspecting the actual file bytes.
- Missing maximum file size check.
- Storage that serves uploaded files from the same origin/domain as the application (increases the blast radius of any stored executable content).

### How to reproduce
Upload a file with a mismatched signature — e.g., an executable or script renamed with an image extension, or sent with `Content-Type: image/png` — and confirm whether the server accepts it. Also try an SVG with an embedded `<script>` tag as an "image" upload.

### Fix
1. Check the **MIME type** sent by the client (`Content-Type`) — necessary but not sufficient on its own.
2. Check the **magic bytes** (the actual content of the file's first bytes) — this is the reliable check, since it doesn't depend on anything the client claims.
3. Check a **maximum size**.
4. Explicitly reject executable extensions.
5. Serve uploaded files from storage **separate from the application's own domain** (S3, Supabase Storage, etc.) so any stored malicious content can't execute in the app's own origin/context.

Useful library in Node: `file-type` (detects the type from content, not from the filename).
