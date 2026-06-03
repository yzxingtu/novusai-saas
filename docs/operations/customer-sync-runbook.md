# Customer Sync Runbook

Customer repositories are downstream delivery repositories for Yudi SaaS. They
must stay thin and record the upstream Yudi base they were synchronized from.

## Required Base Metadata

Each customer repository must keep a `.yudi-base` file at the repository root.
The file must include:

- `upstream`: the Yudi upstream remote or repository URL.
- `base_tag` or `base_commit`: the Yudi release tag or commit used as the
  current customer base.
- `last_synced_at`: the date or timestamp of the latest upstream sync.

JSON is preferred:

```json
{
  "upstream": "git@github.com:example/novusai-saas-yudi.git",
  "base_tag": "yudi-v1.4.0",
  "last_synced_at": "2026-05-11T09:30:00Z"
}
```

Simple key-value files are also accepted by the verifier:

```text
upstream=git@github.com:example/novusai-saas-yudi.git
base_commit=abc1234
last_synced_at=2026-05-11
```

## Sync Flow

1. Reproduce common platform bugs in Yudi first.
2. Fix and verify the change in Yudi.
3. Merge, backport, or tag the Yudi release branch.
4. In the customer repository, synchronize with `merge upstream/<release>` or
   `cherry-pick -x <commit>`.
5. Update `.yudi-base` to record the new `base_tag` or `base_commit` and
   `last_synced_at`.
6. Run the Yudi base verifier before claiming the customer repository is synced.

## Verify Yudi Base Metadata

From the Yudi repository, run:

```powershell
pwsh -File ops/verify-yudi-base.ps1 -Path <customer-repo>
```

If `-Path` is omitted, the script checks the current directory:

```powershell
pwsh -File ops/verify-yudi-base.ps1
```

The verifier exits `0` when `.yudi-base` exists and contains `upstream`,
`last_synced_at`, and either `base_tag` or `base_commit`. It exits `1` and
prints the missing file or fields when the metadata is incomplete.

Passing temporary sample:

```powershell
$tmp = Join-Path $env:TEMP "yudi-base-pass"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
@'
{
  "upstream": "git@github.com:example/novusai-saas-yudi.git",
  "base_tag": "yudi-v1.4.0",
  "last_synced_at": "2026-05-11T09:30:00Z"
}
'@ | Set-Content -Path (Join-Path $tmp ".yudi-base")
pwsh -File ops/verify-yudi-base.ps1 -Path $tmp
```

Failing temporary sample:

```powershell
$tmp = Join-Path $env:TEMP "yudi-base-fail"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
@'
upstream=git@github.com:example/novusai-saas-yudi.git
'@ | Set-Content -Path (Join-Path $tmp ".yudi-base")
pwsh -File ops/verify-yudi-base.ps1 -Path $tmp
```
