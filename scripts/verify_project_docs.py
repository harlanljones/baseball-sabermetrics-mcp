from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    required = (
        "README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md", "SUPPORT.md",
        "CHANGELOG.md", "docs/data-sources.md", "docs/architecture.md", "docs/security-and-operations.md",
        "docs/mcp-best-practices.md",
        "docs/mcp-interface.md", "docs/mcp-interface.json", ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml", ".github/ISSUE_TEMPLATE/data_source_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml", ".github/workflows/quality.yml",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert not missing, f"Missing project documentation: {', '.join(missing)}"
    sources = (ROOT / "docs" / "data-sources.md").read_text(encoding="utf-8")
    for required_text in (
        "openbiomechanics_pitching", "openbiomechanics_hitting", "openbiomechanics_high_performance",
        "CC BY-NC-SA 4.0", "professional sports organizations", "financial analysis firms", "written paid license",
    ):
        assert required_text in sources
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "does not download, bundle, or redistribute baseball data" in readme
    assert "docs/mcp-interface.json" in readme
    print("Project documentation verification passed")


if __name__ == "__main__":
    main()
