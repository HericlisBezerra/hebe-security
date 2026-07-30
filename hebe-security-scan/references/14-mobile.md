# Mobile Security (React Native / Expo)

## No Secrets in the JavaScript Bundle

All API keys and secrets in the JavaScript bundle are extractable — even with Hermes bytecode compilation. The bundle is a file on the device that can be read, decompiled, and searched for strings.

- `react-native-config` values are baked into the bundle at build time. They are not secret.
- `EXPO_PUBLIC_` values are baked into the bundle at build time. They are not secret.
- Environment variables set via `eas.json` or `app.config.js` that end up in the JS bundle are not secret.

The only safe approach: **use a backend proxy** for all third-party API calls that require secret keys. The mobile app calls your server; your server calls the third-party API with the key.

### How the attacker exploits it

- Pulls the installed app's IPA/APK, extracts the JavaScript bundle (even Hermes bytecode can be decompiled/strings-searched), and greps it for API key patterns or known env var names, recovering secrets that were assumed safe because they went through `react-native-config`, `EXPO_PUBLIC_`, `eas.json`, or `app.config.js`.
- Uses the recovered key directly against the third-party API (e.g., OpenAI) at the app owner's expense, bypassing any app-level controls entirely.

### Where to look in the code

- Any direct `fetch`/HTTP call from mobile code to a third-party API endpoint that attaches an `Authorization` header or API key sourced from `react-native-config`, `EXPO_PUBLIC_*`, or values baked in via `eas.json`/`app.config.js`.

```typescript
// BAD: API key in the mobile app
const response = await fetch('https://api.openai.com/v1/chat/completions', {
  headers: { 'Authorization': `Bearer ${OPENAI_API_KEY}` }
});

// GOOD: call your own backend, which holds the key
const response = await fetch('https://your-api.com/ai/chat', {
  headers: { 'Authorization': `Bearer ${userSessionToken}` },
  body: JSON.stringify({ message: userInput }),
});
```

### How to reproduce

- Extract the built app's JS bundle (from the IPA/APK, or from the Metro/EAS build output) and grep it for the third-party provider's key prefix or the exact env var name used in the source. A hit confirms the secret shipped to every device.

### Fix

Route every third-party call that requires a secret key through a backend proxy. The mobile app calls your own server (authenticated with the user's session token); your server holds the secret and calls the third-party API on the app's behalf.

## Secure Token Storage

- **Use `expo-secure-store`** (Expo) or **`react-native-keychain`** (bare React Native) for auth tokens.
- **Never use `AsyncStorage`** — it's unencrypted plaintext on disk. On a rooted/jailbroken device, tokens are trivially readable.

### How the attacker exploits it

- With root/jailbreak access to a device (or physical access plus a backup-extraction tool), reads the app's `AsyncStorage` files directly off disk in plaintext and recovers the user's auth token, allowing full account takeover without needing the user's password.

### Where to look in the code

- Any call storing auth tokens, session tokens, or refresh tokens via `AsyncStorage.setItem`.

```typescript
// BAD: plaintext on disk
await AsyncStorage.setItem('authToken', token);

// GOOD: encrypted in device keychain
await SecureStore.setItemAsync('authToken', token);
```

### How to reproduce

- On a rooted/jailbroken test device (or simulator with filesystem access), locate the app's AsyncStorage backing file and check whether the auth token appears in plaintext.

### Fix

Store auth tokens with `expo-secure-store` (Expo) or `react-native-keychain` (bare React Native), which use the OS-level encrypted keychain/keystore. Never use `AsyncStorage` for tokens or any sensitive value.

## Deep Link Security

Deep links (`myapp://path?param=value`) can be triggered by any app or website. They are an attack surface:

- **Validate and sanitize all parameters.** Never trust deep link input.
- **Never include sensitive data in deep link URLs** (tokens, passwords, user IDs that grant access).
- **Don't perform destructive actions** directly from deep link parameters without user confirmation.

### How the attacker exploits it

- Crafts a malicious deep link (embedded in a webpage, message, or another app) containing manipulated parameters that the victim's app trusts blindly, causing it to navigate to an unintended screen, leak data embedded in the URL, or perform a destructive/sensitive action (account change, deletion, privilege change) without the user confirming.

### Where to look in the code

- Deep link handlers (`Linking.addEventListener`, `expo-linking` handlers, custom URL scheme routing) — check whether parameters are validated/sanitized before use.
- Whether any deep link parameter carries a token, password, or user ID that alone grants access to a resource.
- Whether any deep link directly triggers a destructive action (delete, transfer, disable account) without an in-app confirmation step.

### How to reproduce

- Construct a deep link with unexpected or malicious parameter values (wrong type, injected script/path, an ID belonging to another user) and open it on the app; check whether it's processed without validation or triggers an action without confirmation.

### Fix

- Validate and sanitize every deep link parameter before use.
- Never place tokens, passwords, or access-granting user IDs in a deep link URL.
- Require explicit in-app user confirmation before any destructive action reachable via a deep link parameter.

## Biometric Authentication

A simple boolean success check from biometric auth (`isAuthenticated = true`) can be hooked with tools like Frida on a jailbroken device. Proper biometric auth must use **cryptographic verification**:

1. Server sends a challenge (random nonce)
2. App signs the challenge with a hardware-backed key (Secure Enclave / Strongbox)
3. Server verifies the signature

This way, even if the biometric check is bypassed, the attacker can't forge the cryptographic signature.

### How the attacker exploits it

- On a jailbroken device, uses a runtime instrumentation tool (e.g., Frida) to hook the biometric authentication function and force its boolean result to `true`/success, bypassing the actual fingerprint/Face ID check entirely and gaining access as if authenticated.

### Where to look in the code

- Any biometric auth flow whose outcome is a simple boolean (`isAuthenticated = true/false`) that then gates access locally, with no server-side cryptographic verification step tied to that specific auth event.

### How to reproduce

- On a jailbroken test device, attempt to hook the biometric-auth success callback/function with an instrumentation tool and force a success return value; check whether the app grants access purely on that local boolean without any server-verifiable proof.

### Fix

Implement challenge/response cryptographic verification instead of a local boolean check:

1. Server sends a random challenge (nonce).
2. App signs the challenge using a hardware-backed key (Secure Enclave on iOS / Strongbox on Android), unlocked by the biometric prompt.
3. Server verifies the signature against the stored public key.

This way, even if the local biometric check is hooked/bypassed, the attacker still cannot produce a valid signature without the hardware-backed private key, so the server-side verification fails.
