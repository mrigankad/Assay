# Security policy

Please report vulnerabilities privately through [GitHub security advisories](https://github.com/mrigankad/Assay/security/advisories/new), not public issues. Include the version, steps to reproduce and the impact you see.

Assay is self-hosted. Before exposing it beyond your machine, set a strong `JWT_SECRET_KEY`, keep `ALLOW_SIGNUP=false` or use SSO with `SSO_ALLOWED_DOMAINS`, and leave `ACL_ENFORCEMENT` on.
