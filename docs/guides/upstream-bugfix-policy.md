# Yudi Upstream Bugfix Policy

`novusai-saas-yudi` is the canonical SaaS upstream. Customer repositories are
thin downstream forks or overlays. Any bug that affects shared product behavior
must be fixed in Yudi first, then synchronized downstream.

## 1. Ownership Triage

Before editing code, classify the bug in the ticket or PR description.

| Owner | Bug belongs here when | Fix location |
|---|---|---|
| Yudi upstream | It affects shared SaaS behavior, core security, auth/RBAC, tenant isolation, task queues, notifications, AI runtime, plugin framework, migrations, Docker baseline, shared UI, or any reusable product module. | `novusai-saas-yudi` first |
| Customer repository | It is customer-only workflow, branding, deployment overlay, seed data, customer config, or a private plugin/extension. | Customer repo only |
| Shared extension repository | It is reusable but not core product code, such as a portable plugin or skill package. | Extension repo, then consume from both sides |

If ownership is ambiguous, stop and record the upstream/downstream decision
before implementation. Do not start from a customer repository and later decide
whether to upstream the patch.

## 2. RED Regression In Yudi

For a Yudi-owned bug, reproduce it in `novusai-saas-yudi` with the smallest
focused regression test that fails for the current defect.

```bash
git switch main
git pull --ff-only
git switch -c hotfix/<bug-slug>

# Add the narrow regression first, then prove RED.
python -m pytest tests/path/to/test_bug.py -q
```

Rules:

- The RED test must exercise the real Yudi code path affected by the customer
  report.
- Prefer one focused test over a broad fixture rewrite.
- For AI dialogue paths, follow `.trellis/spec/ai-runtime/testing-discipline.md`:
  label tests as `structural`, `behavioral`, or `smoke`, and avoid weak or
  self-fulfilling assertions.
- Customer-only data may be minimized into generic fixtures; do not commit
  customer names, secrets, or private payloads.

## 3. GREEN Fix In Yudi

Implement the smallest upstream fix that makes the RED regression pass without
adding customer-specific branches.

```bash
# Edit Yudi code and tests.
python -m pytest tests/path/to/test_bug.py -q

# Run the smallest relevant broader check for the touched subsystem.
python -m pytest tests/path/to/related_suite.py -q
```

The fix is acceptable only when:

- The RED regression is now GREEN.
- The relevant subsystem checks pass or any skipped check is explicitly
  recorded with the reason.
- The implementation belongs to shared product code rather than a customer
  overlay.
- Any migration, runtime contract, or public behavior change is documented in
  the owning canonical spec when it becomes a stable rule.

## 4. Submit, Merge, Tag, And Roll Back

Use normal Yudi review and release lines:

- `main` is the product integration line.
- `release/x.y` is the stable customer delivery line.
- `hotfix/*` is for urgent production repairs.

Typical upstream flow:

```bash
git status --short
git add <changed-files>
git commit -m "fix(<area>): <short bug summary>"
git push -u origin hotfix/<bug-slug>
```

After review, merge into the required Yudi line:

```bash
git switch main
git pull --ff-only
git merge --no-ff hotfix/<bug-slug>
git tag yudi-vX.Y.Z
git push origin main yudi-vX.Y.Z
```

If the fix must be backported to a release branch:

```bash
git switch release/x.y
git pull --ff-only
git cherry-pick -x <yudi-fix-commit>
git push origin release/x.y
```

Rollback also starts in Yudi. Revert the upstream commit, verify the rollback,
and then synchronize the revert downstream.

```bash
git switch release/x.y
git pull --ff-only
git revert <yudi-fix-commit>
python -m pytest tests/path/to/rollback_scope.py -q
git push origin release/x.y
```

## 5. Synchronize Customer Repositories

Customer repositories must record their Yudi base tag or commit before and
after sync.

```bash
git remote add upstream <yudi-repo-url> # once per customer repo
git fetch upstream --tags
git describe --tags --always upstream/release/x.y
```

Preferred sync is a merge from the Yudi release line:

```bash
git switch main
git pull --ff-only
git fetch upstream --tags
git merge --no-ff upstream/release/x.y
python -m pytest tests/customer_smoke.py -q
git push origin main
```

For an urgent single fix, cherry-pick with provenance:

```bash
git switch main
git pull --ff-only
git fetch upstream
git cherry-pick -x <yudi-fix-commit>
python -m pytest tests/customer_smoke.py -q
git push origin main
```

The `-x` flag is required for downstream cherry-picks so the customer history
points back to the exact Yudi commit.

## 6. Downstream Patch Discipline

Customer repositories must stay thin. Do not keep long-lived customer-side core
patches in these areas:

- auth, RBAC, and tenant isolation
- task queues and schedulers
- notifications
- AI runtime and dialogue orchestration
- plugin framework and shared plugin host contracts
- migrations and schema baseline
- Docker, compose, CI, and deployment baseline shared by the product
- shared UI components, layout shells, and cross-tenant pages

Allowed downstream differences should use:

- plugins or extension packages
- runtime config and feature flags
- seed data and customer fixtures
- branding assets and copy
- deploy overlays and environment-specific infrastructure

If a customer repository needs a temporary emergency core patch, it must have:

1. A linked Yudi upstream bugfix PR.
2. A named expiry condition, such as `remove after yudi-vX.Y.Z sync`.
3. A follow-up sync task that removes the downstream patch after merge or
   cherry-pick from Yudi.

## 7. PR Checklist

Every upstream-owned bugfix PR must answer:

- Bug owner: `Yudi upstream`, `customer repo`, or `shared extension repo`.
- RED evidence: failing Yudi regression command and failure summary.
- GREEN evidence: passing Yudi regression and relevant subsystem command.
- Release target: `main`, `release/x.y`, or `hotfix/*`.
- Customer sync plan: merge `upstream/release/x.y` or `cherry-pick -x`.
- Rollback plan: upstream revert command and downstream sync path.
- Downstream patch status: confirm no long-lived customer core patch remains.
