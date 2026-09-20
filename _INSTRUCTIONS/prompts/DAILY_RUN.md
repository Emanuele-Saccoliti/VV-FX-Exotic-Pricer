# Daily Codex prompt

Use the following prompt from the repository root:

```text
Continue the VV → SSVI → Heston → C++ DNT roadmap.

Read AGENTS.md and every required project-control file before acting. Inspect the
repository and git state. Select only the first READY milestone in TASK_QUEUE.md.
Implement that milestone or one coherent vertical slice if it cannot safely be
completed in this run.

Preserve existing user changes and public behavior. Add quantitative tests and
run all gates relevant to the changed Python/C++ code. Update TASK_QUEUE.md,
STATE.md, and DECISIONS.md only when appropriate.

Create or reuse the milestone branch, commit only tested work with the prescribed
Conventional Commit message, and push that branch to origin. Never push or merge
main, never force-push, and never weaken numerical tests merely to pass.

Finish with the branch, commit SHA, tests, numerical evidence, limitations, and
the next milestone. If blocked, record the blocker and stop without a broken
commit.
```

## Optional focused continuation

Use this when a milestone remains in progress:

```text
Resume the current IN_PROGRESS milestone from STATE.md. Work only on the next
unfinished acceptance criterion, verify it, update state, commit the coherent
slice, and push the existing milestone branch. Follow AGENTS.md exactly.
```
