# Deployment Security

Vulnerabilities in this category aren't bugs in application logic — they're the difference between a correctly written app and a correctly written app that was shipped carelessly. A perfect codebase can still leak its entire source, its secrets, and its internal error details if the deployment configuration is wrong.

## Debug mode left on in production

### How the attacker exploits it
Frameworks' debug/development modes are designed to help *you* while coding, not to run in front of the public internet. When left on in production, any unhandled error renders a debug page containing the full stack trace, the exact file paths on the server, the values of environment variables, and sometimes an interactive console/REPL. An attacker triggers an error deliberately (malformed input, unexpected type, a route that 500s) specifically to harvest this page.

### Where to look in the code
- Framework config: `DEBUG = True` (Django/Flask), `NODE_ENV` not set to `production`, a debug/verbose flag left on in the deploy environment variables.
- Custom error handlers that render exception details (`error.stack`, `traceback.format_exc()`) directly into the HTTP response instead of a generic message.

### How to reproduce
Trigger an error intentionally (send malformed JSON, an invalid ID type, a missing required field) and inspect whether the response contains a stack trace, file paths, or environment values instead of a generic error message.

### Fix
- Disable debug mode in every production environment variable/config.
- Error handlers return a generic message to the client; log the full stack trace server-side only (Sentry, structured logs) — never in the HTTP response body.

---

## Source maps exposed in production

### How the attacker exploits it
Source maps let DevTools reconstruct your original, unminified source code — including comments, variable names, and logic that was never meant to be readable client-side. If source maps are deployed alongside the production bundle, anyone can open DevTools → Sources and read the entire application's source, including any client-side logic that reveals business rules, internal endpoint structure, or (in the worst case) hardcoded values that should never have been in the frontend at all.

### Where to look in the code
- Build config (`webpack.config.js`, Vite, Next.js `next.config.js`, etc.) — check whether `sourcemap`/`devtool` is enabled for the production build target.
- Deploy output: check whether `.map` files are actually present in the deployed `dist`/`build`/`.next` directory.

### How to reproduce
```bash
# on the local production build output; the published site is Runtime work
find .next/static dist build out -name '*.map' 2>/dev/null | head
# any .map shipped in the deploy output means original source is exposed
```

### Fix
Disable source map generation (or at minimum, do not deploy the generated `.map` files) for production builds. If source maps are needed for error-tracking tools (e.g. Sentry), upload them privately to the tool's own service rather than serving them publicly alongside the bundle.

---

## `.git` directory accessible in production

### How the attacker exploits it
If the deploy process copies the entire project directory (including the hidden `.git` folder) into the web root, and the web server doesn't explicitly block dotfiles, the entire commit history becomes downloadable. This includes every version of every file that was ever committed — meaning any secret that was committed and later "removed" is still sitting in an old commit, fully recoverable with standard tools (`git log`, or automated `.git` dumper scripts).

### Where to look in the code
- Deploy/build scripts: confirm the deployment step doesn't simply copy the whole repo directory as-is into the served path.
- Web server / static file config: confirm dotfiles (`.git`, `.env`, `.htaccess`, etc.) are excluded from being served.

### How to reproduce
```bash
# against a local build/preview of the deploy artifact; the published site is Runtime work
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/.git/HEAD
# a 200 with git ref content means the entire source and history are exposed
```

### Fix
Ensure the deployment pipeline only ships the built output (not the full repo with `.git`), and explicitly configure the web server/CDN to return 404 for any dotfile path. If `.git/HEAD` was ever found accessible, treat every secret ever committed to that repo as compromised and rotate it — the exposure window may have existed for a long time before discovery.

---

## Environment separation

### How the attacker exploits it
Preview/staging deployments (e.g. Vercel PR previews) are often reachable by anyone who has the URL — there's frequently no additional access control beyond obscurity. If a preview environment is configured with production API keys, a production database connection string, or live payment keys, anyone who finds or is sent that preview URL has effectively unrestricted access to production-grade credentials without ever touching the "real" production deployment.

### Where to look in the code
- Environment variable configuration per deployment target (Vercel/Netlify/等 dashboard, or `.env.production` vs `.env.preview` vs `.env.development`).
- Confirm which set of keys (test vs live) is wired to each environment.

| Environment | Purpose |
|-------------|---------|
| Production | Live users, real keys |
| Preview | PR previews, should use test/staging keys |
| Development | Local dev, uses local/test keys |

### How to reproduce
Compare the per-environment variable configuration (names and scopes in the Vercel/Netlify dashboard or `wrangler` config, never values): a production-scoped secret also assigned to Preview is the finding. Do not call env-echo endpoints or trigger third-party actions on a preview; checking the published preview is Runtime work with the owner's authorization.

### Fix
Use fully separate environment variables per environment. Preview deployments must **never** use production API keys, database credentials, or payment keys — treat every preview URL as public by default.

---

## Pre-Ship Checks

Run before every production deploy:
- Run `gitleaks detect --redact` on the repo to scan for leaked secrets across git history.
- Verify `.env` files are listed in `.gitignore`.
- Confirm debug mode / verbose logging is disabled for the production build/environment.
- Check that error pages don't leak stack traces.
- Verify CORS uses exact, approved origins for the installation and any tenant custom domains; never reflect arbitrary `Origin` or combine `*` with credentials.
- Verify source maps are not served publicly; private upload to an error-tracking service is compatible with this check.
- Verify `/.git/` (and other dotfiles) return 404 on the live site.
