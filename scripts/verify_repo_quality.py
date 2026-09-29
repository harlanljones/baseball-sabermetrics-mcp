from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baseball_mcp.cli import build_parser  # noqa: E402


def main() -> None:
    build_parser()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for required in (
        'name = "baseball-sabermetrics-mcp"', 'requires-python = ">=3.10"', 'dependencies = []',
        'license = "MIT"', '[project.urls]', 'Repository = "https://github.com/harlanljones/baseball-sabermetrics-mcp"',
    ):
        assert required in pyproject
    assert "License ::" not in pyproject, (
        "License classifiers are superseded by the SPDX license expression and rejected by setuptools>=77"
    )

    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "permissions:" in workflow and "contents: read" in workflow
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]' in workflow
    assert "verify_openbiomechanics.py" in workflow
    assert "export_mcp_spec.py --check" in workflow
    assert "build_parser" in workflow
    assert "pip wheel" in workflow

    forbidden = {".sqlite3", ".sqlite", ".c3d", ".zip", ".evf", ".eva"}
    bundled = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.casefold() in forbidden
        and ".git" not in path.parts and ".venv" not in path.parts
    ]
    assert not bundled, f"Possible source data/database bundled in repository: {', '.join(bundled)}"
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
    print("repository quality verification passed")


if __name__ == "__main__":
    main()
