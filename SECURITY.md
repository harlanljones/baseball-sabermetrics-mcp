# Security policy

## Supported versions

Security fixes are made on the default branch. Before using a release, review its source and the rights and sensitivity of the data you import.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the repository maintainers. If GitHub private vulnerability reporting is enabled for the repository, use **Security → Advisories → Report a vulnerability**. Otherwise, contact a maintainer through a private channel available to you. Do not publish exploit details in an issue before a fix is available.

Include the affected version or commit, impact, prerequisites, and a minimal reproduction. Do not attach baseball datasets, database files, credentials, or human-subject records; describe a synthetic fixture instead.

## Security model

The intended server transport is local stdio. The server does not implement network authentication. SQL uses a read-only database connection plus a SQLite authorizer, execution timeout, row limit, and serialized response bound. These application checks do not replace operating-system file permissions or correct MCP client configuration. See [Security and operations](docs/security-and-operations.md) for the threat model and limitations.
