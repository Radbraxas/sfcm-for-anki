# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Do not open a public issue.

Include what you found, how to reproduce it, and what an attacker could do with it. We aim to acknowledge reports within 7 days.

## Scope

Especially relevant for this app:

- API keys leaking from the keychain, logs, crash reports or the engine.
- Script injection into Anki cards. Anki runs JavaScript inside cards, so any way to get unsanitized HTML into a generated card is a vulnerability.
- Prompt injection that makes the app do something other than produce cards (for example, sending data somewhere).
- Local-only mode letting data leave the machine.

## Supported versions

Only the latest release receives security fixes during early development.
