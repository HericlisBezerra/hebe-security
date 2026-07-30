# Dependencies

## Known CVEs in direct and transitive dependencies

### How the attacker exploits it
A dependency (direct or transitive) with a known, published CVE is a documented, often weaponized attack path — no original research needed on the attacker's part, just matching your `package.json`/`requirements.txt`/lockfile against public vulnerability databases. A critical CVE in a direct dependency (auth library, ORM, template engine, image processor, etc.) is treated as a High/Critical finding on its own, independent of anything else in the audit.

### Where to look
- Lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `Pipfile.lock`, `poetry.lock`, `Gemfile.lock`, `go.sum`, `composer.lock`) — the actual resolved versions, not just the version ranges in the manifest.
- Direct dependencies first (higher blast radius, easier to reach from user input), then transitive.
- Abandoned dependencies: no commits/releases in a long time, unmaintained, single-maintainer packages with no recent activity — these won't get a patch even if a CVE is found later.

### How to reproduce / detect
Run the audit tool for the ecosystem:
```bash
npm audit            # or: pnpm audit / yarn audit
pip-audit             # Python
bundle audit          # Ruby
govulncheck ./...     # Go
composer audit        # PHP
```
A critical/high finding in a direct dependency is an immediate Critical/High-severity item in the report — cite the CVE ID, the affected package + version, and the fixed version.

### Fix
- Upgrade to the patched version indicated by the audit tool. If a direct upgrade isn't possible (breaking change), evaluate a transitive override/resolution pin as a stopgap, but track it as tech debt.
- Recommend **Dependabot** or **Renovate** for continuous, automated dependency PRs — this is the single highest-leverage fix for this category, since it turns a one-time audit finding into an ongoing process.
- Replace abandoned/unmaintained dependencies with an actively maintained alternative, especially for anything in the security-critical path (auth, crypto, input parsing).
- Run the audit tool in CI on every PR, not just ad hoc, so a newly-disclosed CVE in an existing dependency gets caught on the next build rather than sitting silently.

## Tooling reference by ecosystem

| Ecosystem | Audit tool |
|---|---|
| Node/npm | `npm audit` |
| Node/pnpm | `pnpm audit` |
| Node/yarn | `yarn audit` |
| Python | `pip-audit` |
| Ruby | `bundle audit` |
| Go | `govulncheck` |
| PHP | `composer audit` |
| Cross-ecosystem SAST/SCA | Snyk (Code + Open Source), Semgrep, CodeQL |

Continuous maintenance: **Dependabot** or **Renovate** for auto-PR updates, wired into CI so dependency drift and newly disclosed CVEs surface automatically rather than waiting for the next manual audit.
