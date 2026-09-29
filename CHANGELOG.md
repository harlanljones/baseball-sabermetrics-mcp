# Changelog

Notable changes are recorded here. This project follows Keep a Changelog's section structure; versions use Semantic Versioning.

## [Unreleased]

### Added

- OpenBiomechanics Project CSV catalog/import guidance for pitching, hitting, and high-performance modules.
- MCP tool annotations, output schemas, structured results, stricter argument validation, and bounded query output.
- Current MCP 2026-07-28 per-request metadata/version discovery, legacy interoperability, paged table listings, and per-process tool-call rate limits.
- Generated machine-readable MCP interface documentation and open-source contributor/security guidance.
- GitHub Actions continuous integration workflow (`.github/workflows/quality.yml`) running matrix checks on Python 3.10 through 3.14 across push, pull request, and manual dispatch triggers.

### Changed

- **Breaking:** drop legacy MCP protocol versions `2024-11-05` and `2025-03-26`. Supported versions are now `2025-06-18` and `2025-11-25` (legacy `initialize` handshake) plus `2026-07-28` (modern per-request `server/discover` metadata). Clients pinned to a removed version must re-pin before upgrading.
- **Breaking:** reduce the `query_sql` serialized data cap from 450,000 to 180,000 bytes. Large results now set `truncated: true` sooner; clients must narrow queries or page with smaller limits.
- **Breaking:** page `list_tables` results (`total_count`, `limit`, `offset`, `next_offset`, at most 500 summaries per call) and limit the `baseball://tables` and `baseball://schema` resources to their first page (100 and 10 entries). Clients expecting the full table list must follow `next_offset` via `list_tables` and `describe_table`.
- Unknown resource URIs now report `-32602` for modern requests while legacy requests keep `-32002`.

### Fixed

- Fix editable installs on setuptools 77 and newer by dropping the superseded MIT license classifier; the SPDX `license = "MIT"` expression is retained.
- Fix ingestion CLI startup by declaring the `source` positional with `metavar` instead of an illegal `dest` override; help output still shows `source` and the path is still stored on `source_path`.

## [0.1.0] - 2026-09-24

- Initial local read-only MCP server, Lahman and Retrosheet importers, and public source catalog.
