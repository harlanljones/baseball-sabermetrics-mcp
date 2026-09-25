# Contributing

Thanks for helping improve Baseball Sabermetrics MCP. Contributions should make the local import and read-only query workflow more reliable without bundling third-party data.

## Before opening a pull request

1. Read the [Code of Conduct](CODE_OF_CONDUCT.md), [Security policy](SECURITY.md), [data-source terms](docs/data-sources.md), and [architecture](docs/architecture.md).
2. Keep upstream datasets, release archives, SQLite databases, and human-subject data out of commits and issue attachments.
3. For behavior changes, update the README or focused docs, the MCP interface reference, and `docs/mcp-interface.json` as appropriate.
4. Keep runtime dependencies in the Python standard library unless a concrete need justifies a reviewed dependency.
5. Describe the change, data-source implications, and verification performed in the pull request.

## Local development

Use Python 3.10 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

The verification scripts use only the Python standard library. From the repository root, run:

```sh
python3 -m compileall -q src scripts
python3 scripts/export_mcp_spec.py --check
python3 scripts/verify_mcp.py
python3 scripts/verify_lahman.py
python3 scripts/verify_retrosheet.py
python3 scripts/verify_catalog.py
python3 scripts/verify_readonly.py
python3 scripts/verify_openbiomechanics.py
python3 scripts/verify_mcp_best_practices.py
python3 scripts/verify_mcp_spec.py
python3 scripts/verify_project_docs.py
python3 scripts/verify_repo_quality.py
```

These scripts create temporary fixtures; they do not need public source files. Do not use real third-party or human-subject datasets as test fixtures. `workflow_dispatch` in GitHub Actions runs the same verification set on Python 3.10 through 3.14.

## Pull request checklist

- [ ] The change is scoped and the docs describe user-visible behavior.
- [ ] MCP input and output schemas match runtime behavior; regenerate the interface file when those definitions change.
- [ ] Read-only enforcement remains in place for all query paths.
- [ ] The verification set was run, or any missing run and its reason are described.
- [ ] No source data, database, credentials, or private records are included.
- [ ] Provenance, citations, and data-license caveats remain clear.
