# Security

Do not commit API keys, deployment tokens, private building records or local environment files.

The optional model integration reads `OPENAI_API_KEY` only on the server. The browser receives a boolean configuration status, never the credential. Requests are same-origin checked, size limited and rate limited before they reach the provider. Agent mode sends the user’s question, the six most recent user questions and deterministic tool summaries; it does not attach raw client files or unconfirmed rows.

Client-file intake validates extension and signature, sanitizes filenames, limits file size, avoids macro execution and keeps automatic mappings outside the model until the reviewer confirms them. Local parsing is the default. Optional PDF/image recognition requires per-file consent, uses `store: false`, and does not log or persist the raw upload in the application. Client project delivery packs contain file fingerprints and reviewed registers, not raw uploads or raw table rows.

OpenAI states that API inputs and outputs are not used for training by default. Standard abuse-monitoring logs may be retained for up to 30 days, subject to the provider’s current data controls. `store: false` disables application-state storage for the request; it is not, by itself, Zero Data Retention. Organizations that require stricter retention controls should confirm eligibility and configuration before enabling enhanced mode.

If a credential is exposed, revoke it at the provider, replace the deployment secret and remove it from Git history before publishing the repository.
