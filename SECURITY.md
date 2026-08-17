# Security

Do not commit API keys, deployment tokens, private building records or local environment files.

The optional model integration reads `OPENAI_API_KEY` only on the server. The browser receives a boolean configuration status, never the credential. Requests are same-origin checked, size limited and rate limited before they reach the provider.

Client-file intake validates extension and signature, sanitizes filenames, limits file size, avoids macro execution and keeps automatic mappings outside the model until the reviewer confirms them. Local parsing is the default. Optional PDF/image recognition requires per-file consent, uses `store: false`, and does not log or persist the raw upload in the application. Client project delivery packs contain file fingerprints and reviewed registers, not raw uploads or raw table rows.

If a credential is exposed, revoke it at the provider, replace the deployment secret and remove it from Git history before publishing the repository.
