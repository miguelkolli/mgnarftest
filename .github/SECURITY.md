# Security Policy

MGnarfTest is security- and evidence-sensitive infrastructure. Security reports should preserve the same evidence discipline as the test system itself.

## Reporting a vulnerability

Do **not** place credentials, private exploit details, personal data, private keys, provider tokens or other secrets in a public issue, pull request, discussion or test fixture.

When GitHub private vulnerability reporting is available for this repository, use **Security -> Report a vulnerability** so the report can be handled privately.

If private vulnerability reporting is unavailable, open a minimal public issue that asks the maintainer to establish a private reporting channel. Do not include exploit details or secret material in that issue.

## In scope

Examples of security-relevant findings include:

- bypass of the protected-effect or STABLE-promotion boundary;
- forged, replayed, stale or tampered evidence being accepted as authoritative;
- CI or `pull_request_target` privilege escalation;
- execution of untrusted pull-request code in a privileged context;
- secret or credential disclosure through source, history, logs, artifacts or receipts;
- identity/reviewer forgery or authorization confusion;
- fail-open behavior where unavailable authority, state or evidence becomes permission.

## Evidence expectations

A report should identify the exact MGnarfTest commit, affected path, reproduction conditions and observed result when it is safe to provide those details privately. A claimed fix is not considered verified merely because code changed; applicable tests and evidence must execute successfully.

Do not use real production credentials for a proof of concept. Use synthetic values and the smallest safe reproduction that demonstrates the issue.

## Disclosure

Please allow the maintainer an opportunity to investigate and prepare a fix before publishing exploit details. No response-time SLA is promised by this document.
