# Trellis Onboarding

Use Trellis as the canonical source instead of copying a long workflow into this
command.

Read these entry points:

```bash
cat AGENTS.md
cat .trellis/workflow.md
cat .trellis/spec/guides/trellis-paths.md
python3 ./.trellis/scripts/get_context.py
cat .trellis/spec/backend/index.md
cat .trellis/spec/frontend/index.md
cat .trellis/spec/guides/index.md
```

Then summarize:

- current git/task state
- which Trellis path applies (`fast`, `normal`, or `deep`)
- which canonical spec files are relevant to the user's task
- the lightest safe next step

Keep onboarding short and point back to `.trellis/` when details are needed.
