# Security Policy

## Supported Versions

Flux-runtime is an active research project under continuous development.
We do not maintain separate long-term support branches at this time.
Please use the latest commit on the main branch.

## Reporting a Vulnerability

Flux-runtime is an open-source **research runtime** — not production security
software. That said, we take security seriously and welcome responsible
disclosure of any issues you find.

**Please do NOT open a public issue for security vulnerabilities.**

Instead, please report them through one of these channels:

1. **Preferred** — [GitHub Security Advisories](https://github.com/SuperInstance/flux-runtime/security/advisories/new)
   (private, only project maintainers can see it until a CVE is published).

2. **Alternative** — Email `superinstance@github` with the subject line
   `[flux-runtime security]` and include as much detail as possible:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fix (optional but appreciated)

### What to Expect

- We will acknowledge receipt within **5 business days**.
- We will investigate and aim to provide a status update within **14 days**.
- If the report is accepted, we will work on a fix and coordinate disclosure.
- We will credit researchers in our release notes unless anonymity is requested.

### Scope

We consider the following in scope for security reports:

- Arbitrary code execution through crafted inputs or malicious packages
- Sandboxing escapes in the FLUX VM or capability system
- Denial-of-service vulnerabilities (unbounded resource consumption)
- Information leakage between isolated agents or tiles
- Tampering with the bytecode encoder/decoder pipeline

Out of scope:

- Issues in third-party dependencies (please report upstream)
- Typo / documentation errors
- Feature requests
