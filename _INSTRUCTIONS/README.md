# VV → SSVI → Heston → C++ DNT

This folder is an agentic-development overlay for:

`https://github.com/Emanuele-Saccoliti/VV-FX-Exotic-Pricer`

Copy its contents into the repository root. It does not replace the existing
Python/C++ implementation; it adds the operating contract, roadmap, task queue,
technical decisions, and CI expected by Codex.

## Target pipeline

```text
FX ATM/RR/BF quotes
  → complete Vanna–Volga smile per maturity
  → constrained SSVI projection of sampled VV smiles
  → GK target prices
  → Heston calibration with a C++ Fourier/FFT pricer
  → C++ Heston Monte Carlo
  → FX double-no-touch price, standard error, confidence interval
```

Once each smile has been reconstructed from liquid FX market quotes using
Vanna–Volga, the resulting smiles are projected onto a constrained SSVI
parameterization. This gives a surface that is smooth across strikes and
maturities, has controlled wing behavior, satisfies the enforced static
no-arbitrage conditions, and supplies stable vanilla targets for Heston
calibration. The non-pillar VV samples are synthetic points derived from the
original quotes, so their aggregate weight is limited relative to the liquid
pillars.

## Daily workflow

1. Open the repository in Codex.
2. Use the prompt in `prompts/DAILY_RUN.md`.
3. Codex selects only the first ready milestone in `TASK_QUEUE.md`.
4. It creates `codex/<task-id>-<slug>`, implements the task, runs relevant tests,
   updates project state, commits, and pushes the branch.
5. Review and merge the branch manually. The agent never merges or pushes to
   `main`.

The chosen plan contains 15 substantial milestones. A milestone may span more
than one day when its acceptance criteria are not yet met. Codex must not create
an artificial commit merely to preserve a daily cadence.

## Files

- `AGENTS.md`: binding instructions for Codex.
- `PROJECT_SPEC.md`: scope, interfaces, and quantitative definition of done.
- `ARCHITECTURE.md`: ownership split between Python and C++.
- `ROADMAP.md`: phases and dependency order.
- `TASK_QUEUE.md`: executable backlog with acceptance criteria and commit names.
- `STATE.md`: persistent handoff between independent runs.
- `DECISIONS.md`: architecture decision log.
- `prompts/DAILY_RUN.md`: reusable prompt for each agentic run.
- `.github/workflows/ci.yml`: Python/C++ build and test gate.

## Git policy

The project uses one branch per milestone and Conventional Commits, for example:

```bash
git switch -c codex/M04-ssvi-kernel
git commit -m "feat(surface): implement SSVI total variance kernel"
git push -u origin codex/M04-ssvi-kernel
```

`git commit -v2` is not a Git versioning command. Version numbers belong in tags
or releases; daily work should be represented by meaningful commits.
