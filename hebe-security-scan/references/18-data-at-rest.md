# Sensitive Data at Rest

Provider disk encryption is not application encryption. "Supabase/RDS encrypts at rest" protects you against someone stealing the physical disk. It does nothing against the three ways data actually leaks: a dumped backup, an over-permissive read path, and an employee or contractor with console access. If the column is readable as plaintext once you are inside the database, it is plaintext for every one of those scenarios.

Audit this category whenever the app stores any of: government IDs (CPF/SSN/passport), full card data, bank account numbers, health data, precise location history, private message content, or **credentials belonging to the user** (OAuth refresh tokens, third-party API keys, integration secrets).

## Sensitive Columns Stored in Plaintext

### How the attacker exploits it

- Obtains a database dump — via a leaked backup file in object storage, a misconfigured replica, a compromised admin account, or an SQL injection that reaches `SELECT *` — and reads every sensitive column directly, with no further work.
- Uses an over-broad RLS policy or a service-role key exposed in a serverless function to read the sensitive column across all users, even without a dump.
- Escalates a low-severity read primitive (a debug endpoint, an unfiltered admin list view) into a full PII disclosure, because nothing in the storage layer limits what a read returns.

### Where to look in the code

- The schema/migrations — columns named like `cpf`, `ssn`, `document`, `tax_id`, `card_number`, `iban`, `birth_date`, `health_*`, `access_token`, `refresh_token`, `api_key`, `webhook_secret`, `private_notes`.
- Whether any of them go through an encrypt/decrypt path in the application, or are written with a plain `insert`.
- Integration tables that store per-user third-party credentials — these are almost always plaintext in AI-generated code.
- Whether the app confuses **hashing** with **encryption**: passwords must be hashed (irreversible, see `04-authentication-session.md`); a CPF you need to display back must be encrypted (reversible). Using the wrong one is a real finding in both directions.

### How to reproduce

- Query the table directly with an admin/service connection and confirm the value comes back human-readable.
- Restore or open a recent backup and confirm the same.

### Fix

- Encrypt sensitive columns at the application layer, or with `pgcrypto` in Postgres, so the ciphertext is what lands in the row.
- Prefer **envelope encryption**: a data key encrypts the column, a KMS (AWS KMS, GCP KMS, Vault) holds the master key. This makes key rotation possible without re-encrypting everything by hand.
- Decide per column whether you need it back at all. A CPF used only for one-time verification can be stored as a hash and compared, never decrypted.

## The Encryption Key Lives Next to the Data

### How the attacker exploits it

- Reads the encryption key from the same database, the same repository, or the same `.env` that the dump already exposed — and decrypts everything. The encryption bought nothing; it only added a step.

### Where to look in the code

- A key in a config table, a constant in the source, or an env var on the same host with no separate access boundary.
- Whether anyone who can read the ciphertext can also read the key. If yes, treat the data as plaintext in the report.
- Cross-check `01-secrets-and-env.md` — the same key that fails there fails here.

### How to reproduce

- Trace the decrypt call back to where the key comes from. If that source is reachable with the same credential that reads the row, it is exploitable.

### Fix

- Keep the key in a KMS or secret manager with its own IAM policy, not in the database and not in the repo.
- Ensure the role that can read the table cannot fetch the key.
- Implement rotation before you need it — envelope encryption makes this cheap.

## Backups, Exports and Replicas Inherit the Problem

### How the attacker exploits it

- Finds a `.sql`, `.dump` or CSV export sitting in a public or over-permissive bucket and reads it — backups are routinely stored with weaker access control than the live database.
- Pulls the data from a staging or analytics replica seeded with a production copy, where RLS was relaxed "just for testing".
- Retrieves an old export from a support ticket, a shared drive, or a developer's laptop.

### Where to look in the code

- Backup destination buckets — ACLs, public access blocks, lifecycle/retention rules.
- Any job or script that writes an export (`pg_dump`, scheduled CSV report, "download all data" admin feature) and where it puts the file.
- Whether staging/dev environments are seeded from production, and whether that copy was anonymized. See `16-deployment.md`.

### How to reproduce

- Attempt to list and fetch objects from the backup bucket with an unauthenticated or low-privilege identity.
- Check whether a non-admin can trigger an export endpoint and receive the full dataset.

### Fix

- Encrypt backups independently and restrict the bucket to a dedicated role.
- Anonymize or synthesize data when seeding non-production environments — never restore a raw production dump into staging.
- Set retention so exports do not accumulate indefinitely.

## Sensitive Values Leaking into Logs, Errors and Analytics

### How the attacker exploits it

- Reads PII or tokens from an application log aggregator, an error tracker (Sentry and similar), or an analytics event payload — systems that usually have broader team access and weaker retention controls than the database itself.
- Recovers a token from a stack trace that serialized the whole request body.

### Where to look in the code

- `console.log` / logger calls that print a whole request, user object, or provider response.
- Error handlers that attach the full body or headers to the report.
- Analytics/telemetry event properties carrying an email, document number, or token.
- Third-party SDKs configured without a `beforeSend` scrubber.

### How to reproduce

- Trigger the error path and inspect what actually arrives in the log/error tool.

### Fix

- Redact at the logging boundary with an explicit allowlist of loggable fields, not a denylist.
- Configure the error tracker's scrubbing before shipping.
- Never log a decrypted value — decrypt as late as possible, closest to the use.

## Notes on Scope

- **Mobile devices** are a separate storage surface — token storage in the keychain vs plaintext `AsyncStorage` lives in `14-mobile.md`.
- **Passwords** are hashing, not encryption — `04-authentication-session.md`.
- **Card data** — if the app stores a PAN at all, that is a finding on its own; use the processor's token instead. See `12-payments.md`.
- **Searchability trade-off**: randomized encryption breaks `WHERE` and `LIKE`. If a field must be searchable, say so in the finding and propose a blind index or deterministic encryption for that column specifically, naming the leak it accepts — do not silently recommend something that breaks the feature.
