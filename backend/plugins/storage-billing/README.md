# Storage Billing Reconciliation Plugin

`storage-billing` is an independent plugin that reconciles official object-storage traffic bills and turns them into tenant-facing statements. It is intentionally separated from the provider storage plugins (`qiniu-kodo`, `aliyun-oss`, `tencent-cos`) so storage IO and billing reconciliation remain decoupled.

The plugin only bills against official cloud-provider billing data. `local` storage is always excluded.

## Positioning

- Plugin-owned ledger and statement tables live under the `px_storage_billing_` prefix.
- Tenant visibility is gated by the host plan feature `storage_billing_enabled`.
- Runtime prerequisites are validated at run time; they are not hard manifest dependencies in `plugin.yaml`.
- The plugin never overrides provider invoices, tax documents, or payment settlement. Its responsibility is internal reconciliation and tenant allocation based on official provider billing APIs.

## Official Alignment Strategy

The implementation follows the official billing interfaces exposed by each provider instead of estimating traffic from raw upload/download events.

| Provider | Bill source | Official interface used by this plugin | Settlement mode | Plugin period type | Strict daily schedule | Recommended scope | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qiniu Kodo | `finance_api` | Qiniu Finance API `/billing-api/v2/bill/detail` | `monthly_settled` | `monthly` | No | `account` | Implemented |
| Alibaba Cloud OSS | `bss_openapi` | `DescribeSplitItemBill` | `strict_daily_reconciliation` | `daily` | Yes, default run at `03:00` for `D-3` | `bucket`, `domain`, `account`, `tag` | Implemented |
| Tencent Cloud COS | `describe_bill_detail` | `DescribeBillDetail` | `strict_daily_reconciliation` | `daily` | Yes, default run at `03:00` for `D-2` | `bucket`, `domain`, `account`, `tag` | Implemented |

### Provider Notes

- Qiniu official billing is monthly-settled. The official finance documentation states that pay-as-you-go monthly bills are issued on the 4th and should be queried after the 5th. The plugin therefore keeps Qiniu out of the strict daily pipeline and schedules monthly import on day 6 at `03:00` Asia/Shanghai.
- Alibaba Cloud exposes daily split-item queries, but the official documentation also states that split-product bill details can lag by 48 hours, and split-item details for products such as OSS can lag by up to 72 hours. The plugin keeps a daily `03:00` reconciliation job and supports manual reruns for late-arriving official data.
- Tencent Cloud `DescribeBillDetail` is implemented as the daily official detail source. Tencent's official billing documentation states that high-volume bill detail workloads are better handled with bill-file storage to COS; the current phase still uses the official API path and schedules the stable default daily reconciliation window at `D-2`.

## Billing Periods And Schedules

- Daily reconciliation task: cron `0 3 * * *`
- Default target billing date for Alibaba Cloud OSS daily runs: `D-3`
- Default target billing date for Tencent Cloud COS daily runs: `D-2`
- When no explicit daily billing date is provided, scheduled runs and default manual runs fan out per provider using the rules above
- Qiniu monthly settlement task: cron `0 3 6 * *`
- Qiniu monthly target period: previous month
- Supported period model in plugin data: `daily` and `monthly`
- Serialized run/source/statement payloads include `period_type`, `period_start`, `period_end`, and `period_label`

## Operator Guidance

Operators should treat each provider-specific daily schedule as the canonical source of truth. The plugin fires the daily cron at `03:00` Asia/Shanghai and assumes Alibaba Cloud OSS per-day data is stable at `D-3` while Tencent Cloud COS data aligns with `D-2`. Always confirm those assumptions before running manual reruns and during audit reviews so tenant statements mirror the official invoices.

### Manual Reruns

- Open the `Daily reconciliation run` workflow in the admin UI only after the provider console has delivered the expected billing data for the target date.
- Prefer selecting both `provider` and `billing_date` explicitly. When `billing_date` is omitted, the plugin fans out across the selected daily providers and applies each provider's default official lag rule independently.
- Save any rerun reason in the reconciliation notes and capture the original provider billing timestamp; compare it to the official invoice time range to make sure you are not skipping periods or double-counting.
- If you must rerun multiple providers for the same `billing_date`, confirm each provider's lag window before forcibly including them in the manual job.

### Audit Review

- After the scheduled `03:00` run, review the run payloads to ensure `period_type`, `period_label`, and provider metadata match the official API response. Pay special attention to OSS `D-3` feeds and COS `D-2` feeds because they are the backbone for tenant billing.
- Use the plugin's UI to cross-check daily run IDs, charge rows, and statement totals against the provider console or exported official invoices. A mismatch usually indicates version skew or missing manual reruns.
- Retain a log of manual reruns and their parameters. If an administrator asks for a postmortem, the run history and notes are the canonical audit trail.
- Document any adjustments or reruns in the tenant-facing statement description so downstream support teams can justify variance from the scheduled batch.

## Runtime Prerequisites

For a tenant to use this plugin end-to-end, all of the following must be true:

1. The tenant plan enables `storage_billing_enabled`.
2. The tenant storage driver is one of `qiniu-kodo`, `aliyun-oss`, or `tencent-cos`.
3. The matching storage plugin is installed and enabled at runtime.
4. The admin has configured and validated a provider billing profile.
5. The admin has created at least one valid tenant billing binding.

Notes:

- `local` storage always fails billing preflight and is never charged.
- The prerequisite contract is runtime-based. The plugin does not declare a hard `dependencies.plugins` requirement because package entitlement and driver enablement are checked dynamically.
- Tenant prerequisite APIs expose provider capability metadata so the UI can explain whether a provider supports strict daily reconciliation, monthly settlement only, manual pull, or specific scope recommendations.

## Binding Model

Supported binding scopes:

- `bucket`
- `domain`
- `account`
- `tag`

Provider-specific rules:

- Qiniu phase 1 only supports `account` scope bindings.
- Qiniu phase 1 rejects `official_pass_through`; only reconciled allocation is supported.
- Alibaba Cloud OSS and Tencent Cloud COS can be allocated by `bucket`, `domain`, `account`, or `tag`, depending on how official bill details can be matched back to tenant assets.

## Admin Workflow

1. Install and enable `storage-billing`.
2. Install and enable at least one supported provider storage plugin.
3. Enable the tenant plan feature `storage_billing_enabled`.
4. Configure the active object storage provider in the host system storage settings first.
5. In the plugin admin page, configure only billing-side parameters such as `enabled`, `bill_source`, and `account_identifier`.
6. Validate provider profiles. Runtime credentials and region are resolved from the current host storage configuration, so only the active provider card is shown.
7. Create tenant bindings for the relevant billable scope.
8. Run reconciliation manually, or wait for the scheduled job.
9. Inspect runs, sources, allocation summaries, and export charge rows when needed.

Manual admin actions currently supported:

- Daily reconciliation run
- Qiniu monthly settlement pull
- CSV export for run charges

Manual daily rerun rule:

- If `billing_date` is explicitly provided, one daily run can include multiple daily providers for that same billing date.
- If `billing_date` is omitted, the plugin fans out across the selected daily providers and applies each provider's default official lag rule independently.

## Implementation Spec

- The formal implementation spec is available at [docs/implementation-spec.zh-CN.md](docs/implementation-spec.zh-CN.md).

## Tenant Experience

When tenant prerequisites are satisfied, the tenant portal can:

- View current statement summary
- Browse recent statements
- Inspect statement charge rows
- Export statement charges as CSV
- View provider capability hints and prerequisite failures

If prerequisites are not met, the tenant UI receives structured failure reasons instead of silently showing an empty bill page.

## Known Limitations

- `local` storage is never billable.
- Qiniu is monthly-settled only in this phase and is limited to account-scope billing.
- The plugin aligns to official provider bill data, but final invoice, taxation, and settlement remain owned by the provider platform.

## Official References

- Qiniu Finance API documentation: [https://developer.qiniu.com/af/10420/financial-external-api-documentation](https://developer.qiniu.com/af/10420/financial-external-api-documentation)
- Qiniu bill review guidance: [https://developer.qiniu.com/af/12835/bill_review](https://developer.qiniu.com/af/12835/bill_review)
- Alibaba Cloud `DescribeSplitItemBill`: [https://help.aliyun.com/zh/user-center/developer-reference/api-bssopenapi-2017-12-14-describesplititembill](https://help.aliyun.com/zh/user-center/developer-reference/api-bssopenapi-2017-12-14-describesplititembill)
- Tencent Cloud `DescribeBillDetail`: [https://cloud.tencent.com/document/product/555/19182](https://cloud.tencent.com/document/product/555/19182)
- Tencent Cloud COS billing overview: [https://cloud.tencent.com/document/product/436/36522](https://cloud.tencent.com/document/product/436/36522)
