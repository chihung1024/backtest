# Legacy Portfolio Backtest Lab retirement runbook

This document is the execution plan for retiring `chihung1024/backtest` after the owner confirms that the integrated BacktestStock Portfolio Research page is complete and stable.

## Current phase: draft only

The retirement pull request may be reviewed and tested, but must remain unmerged until explicit owner approval.

Actions that are **not authorized in the draft phase**:

- Merge the retirement pull request.
- Publish the GitHub Pages retirement notice.
- Make the Vercel production API return `410 Gone`.
- Disable GitHub Pages.
- Disable, unlink, or delete Vercel project `portfolio-backtest-api` (`prj_oQizOQM2NvBjNuc448wlJIvxPEpT`).
- Archive or delete repository `chihung1024/backtest`.

## Verified replacement

- Repository: `chihung1024/backteststock`
- Portfolio page: `https://backteststock.chired.workers.dev/portfolio/`
- API prefix: `https://backteststock.chired.workers.dev/api/v3/portfolio/`
- Runtime cutover release: `backup-post-pr50-1fc07b23f5cb`
- Deployment-readiness release: `backup-post-pr51-35fe0e3f9c4f`

Both replacement releases completed production Cloudflare Portfolio v3 smoke tests. PR 51 additionally verified that Cloudflare waits until Vercel health reports the same Git SHA before executing the production backtest smoke.

## Draft PR acceptance gates

The draft is ready for owner review only when all items pass:

1. Backend lint and tests pass with at least the existing coverage threshold.
2. Frontend lint, tests, accessibility audit, and production build pass.
3. Container build passes.
4. GitHub Pages workflow builds the retirement page on a pull request but does not deploy it.
5. Production retirement middleware is inactive in local and preview environments.
6. Forced retirement tests prove `/`, `/health`, and all `/api/v1/*` routes return `410 Gone`.
7. The 410 body contains:
   - `status: retired`
   - `code: legacy_project_retired`
   - replacement URL
   - Vercel deployment SHA
8. The Vercel production acceptance workflow waits for the exact retirement commit SHA, then verifies every legacy endpoint returns 410.
9. No workflow performs repository deletion, Vercel project deletion, Pages disablement, or archival automatically.

## Final execution sequence — requires explicit owner approval

### 1. Final preflight

- Re-run BacktestStock full CI.
- Run production Portfolio v3 smoke against the current `main` SHA.
- Confirm Scanner-to-Portfolio handoff, saved model, shared URL, JSON import/export, and mobile layout manually.
- Create or confirm a final backup release for both repositories.

### 2. Merge the retirement PR

Expected effects after merge:

- GitHub Pages publishes only the migration notice.
- Vercel deploys the production retirement middleware.
- The Vercel retirement acceptance waits for the exact merged SHA and validates 410 responses.

### 3. Observe the retired endpoints

Verify:

- `https://chihung1024.github.io/backtest/` shows the migration notice and replacement link.
- `https://portfolio-backtest-api.vercel.app/health` returns 410 with the exact merged SHA.
- `/api/v1/auth/check`, `/api/v1/assets/search`, and `/api/v1/backtests` all return 410.
- No BacktestStock runtime request reaches the old GitHub Pages or Vercel domains.

### 4. Disable the old hosting resources

Manual operation because the current connectors expose no delete/disable action:

- Vercel project: `portfolio-backtest-api`
- Vercel project ID: `prj_oQizOQM2NvBjNuc448wlJIvxPEpT`
- Vercel team: `team_RMK84iApXJx4LXnh8kandfHP`

After a defined observation period:

- Disconnect Git integration or delete the old Vercel project.
- Disable GitHub Pages for `chihung1024/backtest`.
- Verify the domains no longer serve the legacy application.

### 5. Archive before deletion

- Mark the repository read-only/archived first.
- Keep the final release and source commit recorded in BacktestStock migration documentation.
- Retain the archive for the agreed rollback window.

### 6. Delete the original repository

Delete `chihung1024/backtest` only after a second explicit owner confirmation. Repository deletion is irreversible from the connected tools available in this session and must not be automated by this Draft PR.

## Rollback before external resource deletion

Before Vercel, Pages, or repository deletion, rollback is possible by reverting the retirement merge and redeploying the previous release. After external project or repository deletion, restoration depends on platform retention and backups; therefore deletion is intentionally separated from the retirement merge.
