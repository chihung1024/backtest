from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLACEMENT = "https://backteststock.chired.workers.dev/portfolio/"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(content: str, fragment: str, path: str) -> None:
    if fragment not in content:
        raise SystemExit(f"{path} is missing required retirement fragment: {fragment}")


def forbid(content: str, fragment: str, path: str) -> None:
    if fragment in content:
        raise SystemExit(f"{path} contains forbidden active-runtime fragment: {fragment}")


def main() -> None:
    app = read("frontend/src/App.tsx")
    app_test = read("frontend/src/App.test.tsx")
    index = read("frontend/index.html")
    backend = read("backend/app/main.py")
    backend_test = read("backend/tests/test_api.py")
    pages = read(".github/workflows/pages.yml")
    vercel = read(".github/workflows/vercel-production-smoke.yml")
    readme = read("README.md")
    runbook = read("docs/RETIREMENT.md")

    for path, content in {
        "frontend/src/App.tsx": app,
        "frontend/src/App.test.tsx": app_test,
        "frontend/index.html": index,
        "backend/app/main.py": backend,
        "backend/tests/test_api.py": backend_test,
        ".github/workflows/vercel-production-smoke.yml": vercel,
        "README.md": readme,
        "docs/RETIREMENT.md": runbook,
    }.items():
        require(content, REPLACEMENT, path)

    require(app, "投資組合回測已移至 BacktestStock", "frontend/src/App.tsx")
    require(app, "/api/v3/portfolio/*", "frontend/src/App.tsx")
    forbid(app, "runBacktest", "frontend/src/App.tsx")
    forbid(app, "ConnectionDialog", "frontend/src/App.tsx")
    forbid(app, "checkHealth", "frontend/src/App.tsx")
    forbid(app, "/api/v1/", "frontend/src/App.tsx")

    require(index, 'rel="canonical"', "frontend/index.html")
    require(index, "Portfolio Backtest Lab 已移轉", "frontend/index.html")

    require(backend, "legacy_retirement_enabled", "backend/app/main.py")
    require(backend, "VERCEL_ENV", "backend/app/main.py")
    require(backend, "FORCE_LEGACY_RETIREMENT", "backend/app/main.py")
    require(backend, "HTTP_410_GONE", "backend/app/main.py")
    require(backend, '"code": "legacy_project_retired"', "backend/app/main.py")
    require(backend, '"deployment_sha"', "backend/app/main.py")
    require(backend_test, "test_retirement_mode_returns_gone_for_every_legacy_route", "backend/tests/test_api.py")

    require(pages, "pull_request:", ".github/workflows/pages.yml")
    require(pages, "github.event_name != 'pull_request'", ".github/workflows/pages.yml")
    forbid(pages, "portfolio-backtest-api.vercel.app", ".github/workflows/pages.yml")
    forbid(pages, "VITE_API_BASE_URL", ".github/workflows/pages.yml")

    require(vercel, "status == 410", ".github/workflows/vercel-production-smoke.yml")
    require(vercel, "expected_commit", ".github/workflows/vercel-production-smoke.yml")
    require(vercel, "legacy_project_retired", ".github/workflows/vercel-production-smoke.yml")
    require(vercel, "deployment_sha", ".github/workflows/vercel-production-smoke.yml")

    require(readme, "不合併至 `main`", "README.md")
    require(runbook, "requires explicit owner approval", "docs/RETIREMENT.md")
    require(runbook, "must remain unmerged", "docs/RETIREMENT.md")

    destructive_patterns = [
        "gh repo delete",
        "vercel remove",
        "vercel project rm",
        "DELETE /v9/projects",
        "archive repository",
        "archived: true",
    ]
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        content = workflow.read_text(encoding="utf-8")
        for pattern in destructive_patterns:
            forbid(content, pattern, str(workflow.relative_to(ROOT)))

    print("Retirement Draft PR contract is valid; no irreversible action is automated.")


if __name__ == "__main__":
    main()
