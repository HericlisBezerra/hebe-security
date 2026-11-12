# Secrets and Credentials

## Hardcoded Credentials in Source

### How the attacker exploits it
If a repository is public — or becomes public by accident (misconfigured visibility, forked, leaked, sold, acquired) — any secret sitting in source code is instantly compromised. Attackers also run automated crawlers/bots that continuously scan public GitHub for known key patterns (`sk_live_`, `AKIA...`, `ghp_...`) within seconds of a push, well before a human would notice. This is the single most catastrophic and most common mistake AI coding assistants make: an AI trying to "just make deploy work" will paste a real API key, database password, or private key directly into a config file, script, or even a comment.

### Where to look in the code
Grep for common secret-shaped identifiers and known credential patterns across all source, config, and env-like files. List file names (`-l`), never matching lines, so no value reaches the transcript. Classify the type by which vendor pattern matched (one `grep -l` per pattern); if you must see the line, mask it first, e.g. `sed -E 's/([=:][[:space:]"'\'']*)[^[:space:]"'\'']{4,}/\1<redacted>/g'`:

```bash
# generic patterns (name-based)
grep -rEil '(api[_-]?key|secret|token|password|bearer|private[_-]?key)' \
  --include='*.js' --include='*.ts' --include='*.py' --include='*.rb' --include='*.go' \
  --include='*.php' --include='*.java' --include='*.json' --include='*.yml' --include='*.yaml' \
  --exclude-dir=node_modules --exclude-dir=.git .

# known vendor key formats
grep -rEl '(sk_live_|sk_test_|AKIA[0-9A-Z]{16}|ghp_[0-9a-zA-Z]{36}|glpal-|glpat-|xox[baprs]-|Bearer )' --exclude-dir=node_modules --exclude-dir=.git .
```

Named patterns to specifically check for:
- Stripe secret keys: `sk_live_`, `sk_test_`
- AWS access keys: `AKIA[0-9A-Z]{16}`
- GitHub personal access tokens: `ghp_[0-9a-zA-Z]{36}`
- GitLab personal access tokens: `glpat-`
- Slack bot tokens: `xoxb-` (and other `xox[baprs]-` variants)
- Raw `Bearer ` tokens embedded in code or fixtures
- Connection strings with embedded passwords, e.g. `postgresql://user:password@host`
- Private keys or certificates committed to the repo (`.pem`, `.key` files tracked by git)

Also check whether any `.env` file is tracked by git:
```bash
git ls-files | grep .env
```

And search git **history**, not just the current tree — a secret that was later "removed" in a newer commit still lives in the reflog and in every clone/fork that pulled before the removal:
```bash
git log --all -G 'sk_live_|AKIA|SECRET_KEY' --format='%h %ad %an' --name-only   # pattern or variable name, never a pasted value; no patch text
```

Tooling: **gitleaks**, **TruffleHog** — run as a pre-commit hook and again as a CI job scanning every PR.

### How to reproduce
1. Clone the repo fresh (or check out an old commit) and grep for the patterns above.
2. Run `gitleaks detect --redact -v` against the full history (or `trufflehog git file://. --no-verification`), not just HEAD. TruffleHog verifies keys against providers by default; never run it without `--no-verification` here.
3. Do **not** test a found key against the provider. Record location (file:line or commit) and type, treat it as exposed, and recommend rotation; whether it is still active is for the key owner to check in the provider console.

### Fix
- **Zero secrets in source, ever.** All credentials come from environment variables, injected at runtime.
- `.env`, `.env.local`, `.env.*.local`, and any file containing secrets must be in `.gitignore` **before the first commit** — not added afterward.
- `.env.example` / `.env.sample` should be committed with only variable **names**, never real values. Verify it doesn't accidentally contain a copy-pasted real key.
- **If a secret has already leaked, rotate it immediately.** Deleting the file or force-pushing over the commit is not sufficient — crawlers and the git reflog have already captured it. Rotation is the only real fix.
- Prevention: a pre-commit hook running gitleaks/TruffleHog, plus a CI job that scans every PR before merge.
- Mental test: *"would I be comfortable making this repo open source right now?"* If not, there's a secret in the wrong place. Security through obscurity (hoping nobody looks at a private repo) is not real security — if the system stops being secure the moment someone reads the code, it was never secure.
- Where to actually store secrets in production: Vercel/Netlify env vars (simple deploys), Doppler (sync across environments), 1Password Secrets Automation, AWS/GCP/Azure Secret Manager / Key Vault, HashiCorp Vault (enterprise).
- Third-party tokens that **rotate** (e.g. OAuth refresh tokens per user) belong in the database, not in `.env` — only the "parent" credential (the OAuth `client_secret` itself) belongs in env vars.

---

## Client-Side Environment Variable Prefixes

### How the attacker exploits it
Several frameworks automatically inline any environment variable matching a specific prefix directly into the JavaScript bundle shipped to the browser (or baked into a mobile app bundle) at build time. Once inlined, the value is visible to **anyone** who opens dev tools, views page source, or decompiles the app — there is no server between the attacker and that value. Developers (and AI assistants) frequently misuse these prefixes for values that must stay server-only, assuming the prefix is just a naming convention rather than a literal exposure mechanism.

### Where to look in the code
Check every environment variable name against its framework's public prefix:

| Framework | Client Prefix | Danger |
|-----------|--------------|--------|
| Next.js | `NEXT_PUBLIC_` | Inlined into browser JS at build time |
| Vite | `VITE_` | Inlined into browser JS at build time |
| Expo / React Native | `EXPO_PUBLIC_` | Baked into the app bundle |
| Create React App | `REACT_APP_` | Inlined into browser JS at build time |

Grep specifically for prefixed variables whose *name* suggests something sensitive:
```bash
grep -rn 'process\.env\.NEXT_PUBLIC_\|import\.meta\.env\.VITE_\|EXPO_PUBLIC_\|REACT_APP_' . \
  | grep -iE 'secret|private|service|admin|key'
```
Any match combining a public prefix with a sensitive-sounding name (e.g. `NEXT_PUBLIC_SERVICE_ROLE_KEY`, `VITE_STRIPE_SECRET_KEY`) is very likely a critical exposure.

**What is safe / expected to be client-side:**
- Stripe **publishable** key (`pk_live_*`, `pk_test_*`)
- Supabase **anon** key
- Firebase client config (`apiKey`, `authDomain`, `projectId`) — these are inherently public identifiers, not secrets, and are meant to be paired with server-side rules (RLS/Security Rules)
- Public analytics IDs

**What must NEVER be client-side, under any prefix:**
- Supabase `service_role` key (bypasses all RLS — full database access)
- Stripe **secret** key (`sk_live_*`, `sk_test_*`)
- Any database connection string
- Any third-party API secret key
- JWT signing secrets
- OAuth client secrets

### How to reproduce
1. Build the app for production (`next build`, `vite build`, `expo export`, etc.).
2. Search the built output bundle for the suspected value: `grep -rlE "sk_live|service_role|SECRET" ./dist ./out ./.next` (file names only).
3. If a match is in a `.js` chunk shipped to the browser, it is exposed — confirmed exploitable, no further steps needed since any visitor already has it.

### Fix
- Rename the variable to drop the public prefix, and access it **only** from server-side code (API routes, server components, backend functions) — never from client components or anything bundled for the browser.
- Re-audit the entire `.env` file whenever a new prefixed variable is added: ask "does this need to reach the browser?" before naming it with a public prefix.
- If a sensitive value was already shipped in a client bundle, treat it exactly like a leaked secret: **rotate it immediately** — old bundles remain cached in browsers, CDNs, and archive.org indefinitely.

---

## .gitignore and Environment File Hygiene

### How the attacker exploits it
If `.env` (or any file holding real secrets) is committed even once — before `.gitignore` is set up, or because `.gitignore` was added too late — the values are in git history forever, independent of whether the file is later removed from the working tree.

### Where to look in the code
- Confirm `.gitignore` includes `.env`, `.env.local`, `.env.*.local` and any custom secret file patterns used by the project, and that this was true from the **first commit** of the repo (check with `git log --all --full-history -- .env`).
- Confirm `.env.example` / `.env.sample`, if present, contains only placeholder values (`API_KEY=`, `API_KEY=your_key_here`) and not a real key accidentally left in when the example was created by copying the real file.
- Confirm connection strings anywhere in tracked files don't embed a real password directly in the URL (e.g. `postgresql://user:realpassword@host:5432/db`).

### How to reproduce
```bash
git log --all --full-history -- .env .env.local
git show <commit>:.env   # if any commit shows real-looking values, it's compromised history
```

### Fix
- Add `.gitignore` entries before any secret-bearing file is ever created in the repo.
- Keep `.env.example` as a template with variable names only, reviewed on every PR that adds a new env var.
- If a real value is found in history, rotate it and then decide whether the history itself needs to be scrubbed (`git filter-repo` / BFG) — but rotation is the non-negotiable step; scrubbing history alone without rotating does **not** fix anything.
