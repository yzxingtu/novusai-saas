---
name: onboard
description: "Onboard by following Trellis workflow and spec source-of-truth"
---

Onboarding should point to `.trellis` directly:

```bash
cat .trellis/workflow.md
python3 ./.trellis/scripts/get_context.py
cat .trellis/spec/backend/index.md
cat .trellis/spec/frontend/index.md
cat .trellis/spec/guides/index.md
```

For any onboarding explanation, keep `.trellis/` as the canonical rule source instead of copying long workflow text into this skill.
