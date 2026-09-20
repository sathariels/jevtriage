# jevtriage

**Triage gate for pull requests.** A GitHub Action and small Python CLI that asks [TypeSafe Jev](https://typesafe.ai) (System One) one `Choice` question:

| Verdict | Meaning |
| --- | --- |
| `ready` | Looks safe to merge with normal review depth |
| `needs_review` | Needs human eyes (unclear risk, large or ambiguous change) |
| `risky` | Elevated risk (security-sensitive, destructive, or high blast radius) |

The official `ChoiceAnswer.confidence` is a gate: **`ready` only exits 0 when confidence ≥ threshold** (default `0.8`). Low confidence fails closed to `needs_review` (exit 1).

v0.1 is a **drop-in Action**. Copy one workflow YAML, set `TYPESAFE_API_KEY`, pin a model, get a verdict on every PR.

## Not these nearby tools

| Tool | Niche |
| --- | --- |
| **[HexyeDEV/JevPR](https://github.com/HexyeDEV/JevPR)** | GitHub App + policy router (`LOW` / `NORMAL` / `SPECIALIST` → approve or assign reviewers). A review-routing service, not a CI gate. |
| **[1jehuang/jev-pr-labeler](https://github.com/1jehuang/jev-pr-labeler)** | Semantic labels (`type:`, `area:`, `size:`) via OpenRouter. Taxonomy, not merge readiness. |
| **jevtriage (this repo)** | **Triage gate**: `ready` / `needs_review` / `risky` + confidence fail + marketplace-friendly Action + CLI exit codes. |

Pair with [`jevcheck`](https://github.com/sathariels/jevcheck) contracts if you want upgrades to fail when this question flips. **jevcheck is not a v0.1 dependency** — `fixtures/pr-triage.contract.json` and `fixtures/replay-ready.json` are the replay shape.

## Install

```bash
pip install -e ".[dev]"
export TYPESAFE_API_KEY=...          # live Jev only; never commit this
export TYPESAFE_DEFAULT_MODEL=jev-1.13.0
```

Auth is **`TYPESAFE_API_KEY` only** (`typesafe-sdk`). Unit tests mock the client. This repo does not publish to PyPI in v0.1; the Action installs the checked-out tree.

## GitHub Action

Marketplace-friendly root `action.yml`:

```yaml
# .github/workflows/pr-triage.yml
name: pr-triage
on: pull_request
permissions:
  contents: read
  pull-requests: write
  issues: write
jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - uses: sathariels/jevtriage@v0.1.0   # pin a tag or commit SHA once cut; @main until then
        id: triage
        env:
          TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}
        with:
          model: jev-1.13.0
          apply-labels: true
      - run: echo "${{ steps.triage.outputs.verdict }} ${{ steps.triage.outputs.confidence }}"
```

Until a `v0.1.0` tag exists, use `sathariels/jevtriage@main` (or this PR’s SHA). The step **fails** on exit 1 or 2 — that is the gate. Use `continue-on-error: true` only if you want labels/comments after a non-ready verdict.

This repository’s [example workflow](.github/workflows/example-pr-triage.yml) runs the same Action with `answers: fixtures/replay-single-ready.json` so default CI never calls TypeSafe.

### Inputs

| Input | Default | Notes |
| --- | --- | --- |
| `model` | `TYPESAFE_DEFAULT_MODEL` | Required pin. `latest` / `preview` / empty rejected |
| `min-confidence` | `0.8` | Official `ChoiceAnswer.confidence` floor for exit 0 |
| `allow-unpinned` | `false` | Production stay `false` |
| `apply-labels` | `false` | Writes `jev:ready`, `jev:needs-review`, `jev:risky` |
| `github-token` | `${{ github.token }}` | PR fetch + optional labels |
| `pull-request` | event PR number | Used to fetch title/body/diff |
| `repository` | `${{ github.repository }}` | `owner/name` |
| `title` / `body` / `diff-path` | empty | Overrides; skip GitHub fetch when you pass them |
| `answers` / `case` | empty | Fixture replay (CI / no key) |
| `max-diff-chars` | `32000` | Unified diff cap (~20–40k) |
| `python-version` | `3.12` | |

### Outputs

| Output | Source |
| --- | --- |
| `verdict` | `ChoiceAnswer.choice` (`ready` / `needs_review` / `risky`) |
| `confidence` | official `ChoiceAnswer.confidence` in `[0, 1]` |
| `model` | `SystemOneResponse.model` |

## CLI

```bash
# Live (needs TYPESAFE_API_KEY). Fetches the PR via GITHUB_TOKEN.
jevtriage --repo owner/name --pr 123 --model jev-1.13.0

# Local files
jevtriage --title "Fix typo" --body "nits" --diff pr.diff --model jev-1.13.0

# Replay (no key) — jevcheck-style fixture
jevtriage --answers fixtures/replay-single-ready.json --model jev-1.13.0
jevtriage --answers fixtures/replay-ready.json --case auth-bypass --model jev-1.13.0
```

Stdout is one JSON object (`verdict`, `confidence`, `probabilities`, `model`, `usage`, `truncated`). A one-line summary goes to stderr. When `GITHUB_OUTPUT` is set, the Action outputs are appended.

### Environment

| Variable | Role |
| --- | --- |
| `TYPESAFE_API_KEY` | **Required** for live calls. The only auth env. |
| `TYPESAFE_DEFAULT_MODEL` | Pin when `--model` / Action `model` is empty |
| `TYPESAFE_BASE_URL` | Optional SDK API root |
| `GITHUB_TOKEN` / `GH_TOKEN` | Fetch the PR; apply labels if requested |
| `GITHUB_REPOSITORY` | Default `--repo` |
| `GITHUB_OUTPUT` | Write Action outputs |

## Exit codes

| Code | When |
| --- | --- |
| **0** | Verdict is `ready` **and** `confidence` ≥ `--min-confidence` |
| **1** | Verdict is `needs_review`, **or** `ready`/`needs_review` below the confidence threshold |
| **2** | Verdict is `risky`, **or** a config/API/identity error |

Exit **2** is shared on purpose (fail closed). Distinguish them from stdout: a successful call has `verdict`; a failure has `"error"`. `risky` still writes `verdict` + Action outputs before exiting 2. Config errors (missing key, unpinned model, bad replay) also exit 2 and print `{"error": "..."}`.

Label apply failures are logged to stderr and **do not** change the verdict exit code.

## What Jev sees

System One `state` is a JSON object (official SDK: string or object):

- `title`, `body` (body capped at 8k chars)
- `diff` — unified diff, capped at 32k chars by default, with a visible truncation note
- `files` + `stats` when provided or when the GitHub compare payload is used
- `jevtriage_notes` when anything was truncated or the diff was omitted

The only question is a `Choice` named `triage` with **exactly** the three criteria above. Official fields only (`instructions`, `criteria`). The gate uses official `choice` + `confidence` + `probabilities` — no invented confidence field.

## Model pinning

Production mode rejects empty names and floating aliases (`jev-latest`, `jev-preview`, or any name containing `latest` or `preview`). A documented TypeSafe catalog pin as of 2026-09-19 is `jev-1.13.0`. Pass `--allow-unpinned` only for experiments.

The response `model` must match the requested pin (exact string). An opted-in alias may resolve to a concrete version.

## Optional labels

With `--apply-labels` / `apply-labels: true` and `GITHUB_TOKEN`:

- `jev:ready`
- `jev:needs-review`
- `jev:risky`

Other `jev:*` triage labels on the PR are removed so only one remains.

## jevcheck (optional)

`fixtures/pr-triage.contract.json` is a v0.1 jevcheck contract for this exact question. `fixtures/replay-ready.json` is a keyed replay (`docs-typo`, `large-ambiguous`, `auth-bypass`). After you add `jevcheck` to a repo:

```bash
jevcheck eval fixtures/pr-triage.contract.json \
  --candidate-model jev-1.13.0 \
  --answers fixtures/replay-ready.json
```

v0.1 of jevtriage does not install or invoke jevcheck.

## Develop

```bash
pip install -e ".[dev]"
pytest
python -m jevtriage --answers fixtures/replay-single-ready.json --model jev-1.13.0
```

This repo’s default CI runs unit tests (mocked client) and a wheel/sdist smoke on the fixture. No live TypeSafe call.

Verified System One contract: [docs.typesafe.ai/sdk/python.md](https://docs.typesafe.ai/sdk/python.md). Package: `typesafe-sdk`.

## License

MIT. See [LICENSE](LICENSE).
