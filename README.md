# hebe-security

**Security review for coding agents, scoped to the change by default.**

Version **2.5.0** works with Codex, Claude Code and other assistants that support
agent skills. HeBe reviews the current diff and affected trust boundaries; it does
not scan the entire project on every invocation. The 18-category playbook remains
available for an explicitly requested HeBe Baseline.

## Install

```bash
git clone https://github.com/HericlisBezerra/hebe-security.git
```

Copy `hebe-security-scan/` to your agent's user skills directory:

- Codex: `~/.codex/skills/`
- Claude Code: `~/.claude/skills/`

For a shared codebase on the same machine, link both installations to one checkout
instead of keeping independent copies. Preserve existing skills before replacing
them; do not copy over a link assuming it is a separate installation. New sessions
load the updated skill.

## Usage and scope

In Codex, invoke `$hebe-security-scan`; in Claude Code, use `/hebe-security-scan`.
Include a PR, commit, diff or specific question, or invoke it in a task whose change
is already clear. If the target is unclear, the skill asks which change to review.

| Work | Behavior |
|---|---|
| Implementing sensitive code | Relevant preventive guidance, without automatically launching an audit |
| PR or update | Change review: diff, affected controls and necessary dependencies |
| Release review | Reuse applicable source evidence; inspect remaining changes, configuration, migrations, artifact identity and rollback |
| Consequential change to access, tenant authority, money or privileged execution | Focused independent source review using the installed Cloudflare skill |
| Explicit comprehensive source audit or complete audit artifacts | Cloudflare's native full workflow and selected profile |
| Explicit HeBe-only Baseline | HeBe's 18 applicable categories |
| Deployed behavior | Separately authorized Runtime checks, with operational evidence kept distinct |

Unchanged checks are not repeated when their evidence remains applicable. Relevant
unchanged dependencies may still need inspection. A scoped result is not a claim
that the entire application is secure, and finishing the day does not itself
trigger another audit.

## Cloudflare integration

The separate [Cloudflare security-audit skill](https://github.com/cloudflare/security-audit-skill)
is an optional dependency for the delegated and full workflows. Install it in the
same agent environment; it is not vendored in this repository. Read its current
instructions when invoked.

HeBe chooses between focused guidance and a full audit without running two complete
audits in parallel. A **quick** Cloudflare audit still uses its full native workflow
with partial coverage; it is not silently replaced by guidance. Missing dependency,
reviewer, execution sandbox or sufficient budget is reported with the affected gap.
HeBe does not waive Cloudflare's validation or execution requirements.

## Jev-assisted decisions

When review presents a meaningful semantic fork, Jev can suggest which evidence to
inspect next, prioritize candidate paths, or flag possible duplicate root causes.
Questions are batched over small non-secret summaries, not asked for every file.
Clear decisions, arithmetic, hashes and permission rules do not need a model call.

Use configured Jev MCP tools when available. Otherwise the shared Python helper
uses the standard library and a fixed TypeSafe TLS endpoint:

```bash
python3 hebe-security-scan/scripts/jev_decide.py < bounded-decision.json
```

See [the decision protocol](hebe-security-scan/references/jev-decisions.md) for the
request schema and an example. Credentials come from `TYPESAFE_API_KEY` or an
existing macOS Keychain entry; the helper never creates a secret file or prints a
key. The historical default service is `ai.typesafe.hebe-fast-jev`; override its
name with `HEBE_SECURITY_JEV_KEYCHAIN_SERVICE` when needed.

Calls send the supplied summary to TypeSafe and may incur provider charges. Prepare
safe inputs: the helper **does not redact secrets**. It caps requests, validates all
answers, refuses redirects, and makes no automatic retry. Missing credentials or
invalid responses return unavailable advice; the reasoning agent continues with
its actual evidence and reports relevant limits.

**Jev advice never confirms a vulnerability, sets final severity, discards an
unresolved candidate, approves a deployment, grants authorization or substitutes
for independent review.** It executes no returned suggestion. Its uncertainty
thresholds are operational heuristics, not calibrated security guarantees.

## Coverage and evidence

The 18 categories cover secrets, authorization, database rules, sensitive data at
rest, authentication, hidden endpoints, race conditions, input validation,
injection, mass assignment, abuse, payments, AI/LLM integrations, mobile, headers,
deployment and dependencies. The catalog and references load only when needed.

Findings require a concrete trust boundary, attack path, impact and evidence.
Distinguish confirmed findings from hypotheses and untested conditions. Fixes are
applied only when requested and need relevant regression verification.

Source review and deployed checks have different execution boundaries. Active
security tests use appropriate isolated fixtures or staging; the workflow does not
run destructive, load-generating or data-mutating production probes. A provider
capacity error is not proof of an incompatible skill or an audit pass. The skill
cannot automatically replace a main model that has stopped executing.

Installation-specific profiles stay local and are excluded from the public package.
The shared methodology does not hard-code Claude model aliases for Codex.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

The helper contract tests cover malformed answers, probability validation,
uncertainty, missing credentials, refusal of redirects and absence of action
authority. These are tooling checks, not an application security audit or proof of
classification accuracy. Live Jev calls are separate and are not run by unit tests.

## License

MIT — see [LICENSE](LICENSE). Built by HeBeDigital
([@HericlisBezerra](https://github.com/HericlisBezerra)). Incorporated material and
its license are preserved in [ATTRIBUTION.md](hebe-security-scan/ATTRIBUTION.md).
