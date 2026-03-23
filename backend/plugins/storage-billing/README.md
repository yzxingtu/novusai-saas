# Storage Billing Reconciliation Plugin

This plugin is the standalone home for object-storage traffic billing reconciliation.

Current scaffold:

- Host-facing contract only: `manual_entitlement` tenant policy, official-bill-only scope, and the fixed `03:00` daily reconciliation task.
- Placeholder admin and tenant APIs so the plugin can be installed and expanded without changing host code paths again.
- Local storage is intentionally excluded from billable scope.

Planned implementation slices:

1. Provider adapters for Qiniu Kodo, Alibaba Cloud OSS, and Tencent Cloud COS official billing APIs.
2. Plugin-owned ledger tables under the `px_storage_billing_` prefix.
3. Daily settlement generation and tenant statement export.
4. Optional tenant UI for bill overview and statement drill-down.
