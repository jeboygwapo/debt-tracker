# GitHub Actions Workflows

This directory holds the CI/CD pipeline for `debt-tracker` plus three
**reusable workflows** intended for re-use across other projects in the
`claude_projects` monorepo.

## File map

| File | Purpose | Type |
|---|---|---|
| `ci.yml` | Test, image build on `main` push | Top-level |
| `cd.yml` | Deploy to Fly.io after CI succeeds on `main` | Top-level |
| `backup.yml` | Weekly Postgres CSV export to artifact | Top-level |
| `_python-test.yml` | Generic pytest job (pip cache, JUnit, markers) | Reusable (`workflow_call`) |
| `_docker-build.yml` | Generic Docker build + optional push | Reusable (`workflow_call`) |
| `_fly-deploy.yml` | Fly.io deploy + health probe + auto-rollback | Reusable (`workflow_call`) |

The `_*.yml` prefix is a convention — these files **cannot run on their
own**, only via `uses:` from a top-level workflow.

---

## Required secrets

Set these in **repo Settings → Secrets and variables → Actions**:

| Secret | Used by | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | Auto-provided by GHA | GHCR push, deployment status |
| `FLY_API_TOKEN` | `cd.yml`, `backup.yml` | Fly.io deploys + DB proxy |
| `DB_PASSWORD` | `backup.yml` | Postgres password for CSV export |
| `SECRET_KEY` | `backup.yml` | App secret (for Alembic env loading) |

For other projects adopting these workflows, only `GITHUB_TOKEN` is always
free; everything else depends on which reusable workflows you wire in.

---

## Adopting these in a new project

Copy the three reusable workflows into your new repo:

```bash
mkdir -p .github/workflows
cp /path/to/debt-tracker/.github/workflows/_python-test.yml .github/workflows/
cp /path/to/debt-tracker/.github/workflows/_docker-build.yml .github/workflows/
cp /path/to/debt-tracker/.github/workflows/_fly-deploy.yml .github/workflows/
```

Then create your own top-level `ci.yml` / `cd.yml` that calls them. Examples
below.

---

## Reusable workflow: `_python-test.yml`

Generic pytest runner.

### Inputs

| Input | Type | Default | Description |
|---|---|---|---|
| `python-version` | string | `"3.13"` | Python version to install |
| `requirements-files` | string | `"requirements.txt"` | Newline-separated list of requirements files (installed in order) |
| `pytest-args` | string | `""` | Extra args appended to pytest |
| `marker-filter` | string | `""` | Pytest `-m` expression |
| `test-path` | string | `"tests/"` | Path passed to pytest |
| `results-name` | string | `"pytest-results"` | Artifact name for JUnit XML |
| `timeout-minutes` | number | `15` | Job timeout |
| `working-directory` | string | `"."` | Relative working dir |
| `install-playwright-browsers` | boolean | `false` | Run `playwright install --with-deps chromium` after pip |
| `env-json` | string | `"{}"` | JSON object of extra env vars to inject |

### Outputs

| Output | Description |
|---|---|
| `result` | `success` or `failure` |

### Example: unit + smoke job

```yaml
jobs:
  unit:
    uses: ./.github/workflows/_python-test.yml
    with:
      requirements-files: |
        requirements.txt
      marker-filter: "not e2e and not smoke"
      results-name: unit-results
      env-json: '{"SECRET_KEY": "ci-test"}'

  smoke:
    uses: ./.github/workflows/_python-test.yml
    with:
      requirements-files: |
        requirements.txt
        requirements-dev.txt
      test-path: "tests/smoke/"
      marker-filter: "smoke"
      results-name: smoke-results
```

---

## Reusable workflow: `_docker-build.yml`

Builds with Buildx + GHA layer cache. Optionally pushes to a registry.

### Inputs

| Input | Type | Default | Description |
|---|---|---|---|
| `image-name` | string | (required) | Fully-qualified image name |
| `dockerfile-path` | string | `"Dockerfile"` | Relative to context |
| `context` | string | `"."` | Build context |
| `push` | boolean | `false` | Push image to registry |
| `registry` | string | `"ghcr.io"` | Registry hostname for docker login |
| `registry-username` | string | `""` (uses `github.actor`) | Registry user |
| `extra-tags` | string | `""` | Additional `docker/metadata-action` tag rules |
| `platforms` | string | `"linux/amd64"` | Build platforms |

### Secrets

| Secret | Description |
|---|---|
| `registry-password` | Registry password/token. Defaults to `GITHUB_TOKEN` when targeting GHCR. |

### Outputs

| Output | Description |
|---|---|
| `image-tag` | First (canonical) tag produced (e.g. `ghcr.io/owner/repo:sha-abc123`) |
| `image-digest` | Image digest (`sha256:...`) |

### Example: build + push image

```yaml
jobs:
  image:
    needs: [unit, smoke]
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write
    uses: ./.github/workflows/_docker-build.yml
    with:
      image-name: ghcr.io/${{ github.repository }}
      push: true
```

---

## Reusable workflow: `_fly-deploy.yml`

Deploys a Fly.io app, probes health, auto-rolls-back on failure, and writes
a deployment status to GitHub.

### Inputs

| Input | Type | Default | Description |
|---|---|---|---|
| `app-name` | string | (required) | Fly.io app name |
| `fly-host` | string | (required) | Public hostname for health probe |
| `region` | string | `""` | Informational only |
| `image-tag` | string | `""` | Pre-built image to deploy. Empty = build from source. |
| `health-path` | string | `"/api/healthz"` | Health endpoint path |
| `health-timeout-seconds` | number | `60` | Total health-wait budget |
| `auto-rollback` | boolean | `true` | Auto-rollback on failed health |
| `environment` | string | `"production"` | GitHub Environment name |

### Secrets

| Secret | Description |
|---|---|
| `FLY_API_TOKEN` | Fly.io org or app-scoped token (required) |

### Outputs

| Output | Description |
|---|---|
| `release-version` | Fly release version after deploy (e.g. `v123`) |
| `health-status` | `healthy`, `rolled-back`, or `failed` |

### Example: deploy on CI success

```yaml
jobs:
  deploy:
    if: github.event.workflow_run.conclusion == 'success'
    permissions:
      contents: read
      deployments: write
    uses: ./.github/workflows/_fly-deploy.yml
    with:
      app-name: my-app
      fly-host: my-app.fly.dev
    secrets:
      FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

---

## Adding a new test layer (e.g. `contract`)

1. **Register the marker** in `pytest.ini`:

   ```ini
   markers =
       contract: contract tests against external APIs
   ```

2. **Add a job in `ci.yml`** that calls `_python-test.yml`:

   ```yaml
   contract:
     name: Contract
     uses: ./.github/workflows/_python-test.yml
     with:
       test-path: "tests/contract/"
       marker-filter: "contract"
       results-name: contract-results
   ```

3. **(Optional) Gate `build-image`** on the new job by adding it to `needs:`.

That's it — no changes to the reusable workflow needed.

---

## Troubleshooting

### `No module named playwright` in e2e job

The e2e job needs `pytest-playwright`, which lives in `requirements-dev.txt`,
not `requirements.txt`. Install both:

```yaml
- name: Install dependencies (runtime + dev)
  run: |
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
```

### Postgres health check times out in compose

Check `docker compose logs db` in the failure-artifacts upload. Usually one
of:
- `pg_isready` returns 1 because Postgres is still initializing — bump
  `start_period` in the compose healthcheck.
- App container reports `password authentication failed` — `DATABASE_URL`
  in the app env doesn't match the db env.

### `flyctl deploy` hangs or times out

The deploy reusable workflow uses `--remote-only`, so the build runs on
Fly's builders. If the builder is busy this can wait several minutes.
Increase `health-timeout-seconds` if your app boot is slow.

### Auto-rollback fired but app still broken

`_fly-deploy.yml` rolls back to the *previous successful release*. If the
last few releases were all bad, you may need to roll back further:

```bash
flyctl releases list --app <app-name>
flyctl releases rollback <known-good-version> --app <app-name> --yes
```

### Image build cache miss on every run

`docker/build-push-action` uses `cache-from: type=gha` /
`cache-to: type=gha,mode=max`. Cache keys are namespaced by branch — first
build on a new branch is a full miss. Subsequent builds on the same branch
hit. Don't worry about it on `main`.

---

## Pipeline conventions used here

- **Concurrency:** `ci-${{ github.ref }}` cancels in-progress runs on the
  same ref. `cd-main` does NOT cancel — deploys must complete.
- **Test markers:** `smoke` (fast, in-process), `e2e` (Docker + Playwright).
  Default run is `not e2e and not smoke`.
- **Image tags:** `sha-<short-sha>` (immutable) + `latest` on default
  branch. Semver tag (`v0.x.y`) created post-deploy by `cd.yml`.
- **Branching:** Master Jayvee enforces `main` / `develop` / `feature/*`.
  CI runs on every branch; CD runs only when CI succeeds on `main`.

---

## Pipeline log location for debugging

- **GitHub UI:** the run page under Actions shows per-job logs and the
  deploy summary written to `$GITHUB_STEP_SUMMARY`.
- **CLI:** `gh run list --workflow ci.yml` then `gh run view <id> --log`.
- **Failure artifacts:** `e2e-failure-artifacts` (compose logs + Playwright
  traces), retention 14 days.
- **Test result XMLs:** `unit-integration-results`, `smoke-results`,
  `e2e-results` artifacts, retention 14 days.

---

## Pipeline runtime budget

| Layer | Budget | Notes |
|---|---|---|
| Unit + integration | < 30 s | No external services |
| Smoke | < 60 s | ASGI transport, no Docker |
| E2E (Ephemeral) | < 5 min | Includes `docker compose build` |
| Image build & push | < 3 min | GHA cache hit |
| Fly deploy + health | < 90 s | Includes 60 s health wait |

Total CI on a non-main push (no image build, no deploy): **~6 min** worst case.

Total deploy on `main` (CI + image + deploy): **~10 min** worst case.
