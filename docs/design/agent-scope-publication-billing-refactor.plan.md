# Agent Scope, Publication, and Billing Refactor

> **[ARCHIVED]** This design document describes the **legacy** scope model. The current model uses five canonical `ResourceScopeEnum` values (`global_shared`, `admin_only`, `all_tenants`, `admin_and_selected_tenants`, `selected_tenants`) with `owner_tenant_id` and `resource_tenant_assignments`. See `.cursorrules` for the current specification.

## Status

Draft for implementation.

## Goal

Replace the current mixed agent scope and usage-stat design with a clean model:

1. Platform decides whether an agent is available to a tenant.
2. Tenant decides whether that agent is published to tenant users.
3. All tenant admin and tenant user consumption is billed to the tenant.
4. Historical billing attribution must not drift after later config changes.
5. Old aggregated usage stats are removed instead of patched.

## Explicit Breaking Decision

This refactor is destructive by design because the project is not in production yet.

The following legacy path will be removed, not preserved:

- `ai_usage_stats`
- `UsageStat`
- `UsageStatRepository`
- `MeteringService`
- Admin and tenant APIs that read from `ai_usage_stats`
- Frontend pages that assume the old aggregated stats schema

No compatibility layer will be kept for the old stats model.

## Problems in the Current Design

### 1. Agent visibility responsibilities are mixed

The current `Agent` model and related services mix several different concerns:

- resource ownership
- platform-to-tenant distribution
- endpoint audience filtering
- tenant-internal access control
- tenant-user publication

This is currently spread across:

- `scope`
- `target_audience`
- `resource_tenant_assignments`
- `agent_access`

That creates duplicated decision logic in repositories, services, router logic, and chat APIs.

### 2. Usage stats are not billing-grade

Current aggregated stats only group by:

- tenant
- user
- model
- request type
- date

This is not enough for future billing because it cannot answer:

- which agent caused the consumption
- whether the agent was platform-owned or tenant-owned
- whether the call came from tenant admin or tenant user
- whether the tenant user call was allowed through tenant publication
- what the agent ownership and publication state was at the moment of billing

### 3. Historical attribution can drift

If billing is reconstructed from current agent state, the result changes when:

- an agent is unpublished later
- a platform assignment is removed later
- an agent changes owner semantics later
- a tenant changes publication rules later

Billing data must be immutable at call time.

## Target Domain Model

### A. Agent

`Agent` becomes the agent definition and ownership model only.

New semantics (superseded — see `.cursorrules`):

- `owner_tenant_id`: nullable (platform-owned = NULL, tenant-owned = tenant ID)
- `scope`: one of `global_shared | admin_only | all_tenants | admin_and_selected_tenants | selected_tenants`

Rules:

- `admin_only` → platform-only internal agent
- `all_tenants` → available to all tenants
- `admin_and_selected_tenants` / `selected_tenants` → available only to assigned tenants via RTA
- tenant-owned → scope = `all_tenants`, `owner_tenant_id` = tenant ID

### B. ResourceTenantAssignment

Keep `resource_tenant_assignments`, but narrow its responsibility:

- it only answers whether a platform-owned resource is distributed to a tenant
- it is only used when scope requires tenant assignments (selected_tenants / admin_and_selected_tenants)

It must no longer participate in tenant-user publication semantics.

### C. TenantAgentPublication

Add a dedicated tenant publication table.

Purpose:

- tenant decides whether an available agent is exposed to tenant users

Suggested fields:

- `tenant_id`
- `agent_id`
- `enabled_for_users`
- `access_type`
- `tenant_user_role_ids`
- `tenant_user_ids`
- `org_node_ids`
- `published_at`
- `published_by`

This replaces the tenant-user publication part currently hidden inside `agent_access`.

### D. AgentAccess

`AgentAccess` is split by responsibility.

Keep only endpoint-internal role restriction data that is still needed.

Recommended outcome:

- platform admin access restriction stays separate if needed
- tenant admin access restriction stays separate if needed
- tenant user publication rules move to `TenantAgentPublication`

If a field is only about tenant-user publication, it must be removed from `AgentAccess`.

## Billing and Usage Fact Model

## Decision

Do not create new aggregated usage stats as the source of truth.

Use the per-call record as the single billing fact source.

That means the existing `AICallLog` should be upgraded into the immutable billing ledger and become the only authoritative source for:

- billing
- tenant usage summary
- user usage summary
- agent usage ranking
- model distribution
- admin analytics

The old `ai_usage_stats` table is removed entirely.

## Why use per-call ledger as the source of truth

The project already records one row per call in `ai_call_logs`.

That shape is much closer to a real billing ledger than the current aggregated stats table.

Instead of maintaining both:

- per-call log
- aggregated stats table

we keep one fact source and query or aggregate from it.

This removes:

- duplicate writes
- consistency bugs
- rollback mismatches
- drift between logs and stats

## AICallLog required upgrades

`AICallLog` must store immutable attribution fields captured at call time.

Existing useful fields already present:

- `tenant_id`
- `user_id`
- `user_type`
- `agent_id`
- `conversation_id`
- `provider_id`
- `model_id`
- `request_type`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `cost`
- `status`
- `latency_ms`

New fields to add:

- `billing_tenant_id`
- `actor_user_id`
- `actor_user_type`
- `access_channel`
- `agent_owner_type`
- `agent_owner_tenant_id`
- `agent_resource_scope`
- `tenant_publication_id`
- `publication_enabled_snapshot`
- `publication_access_type_snapshot`

Field notes:

- `billing_tenant_id`
  - the tenant that pays for the call
  - for tenant admin and tenant user calls, this is always the current tenant
- `actor_user_id`
  - caller id at call time
- `actor_user_type`
  - `platform_admin | tenant_admin | tenant_user`
- `access_channel`
  - `admin_internal | tenant_admin | tenant_user`
- `agent_owner_type`
  - snapshot from agent ownership at call time
- `agent_owner_tenant_id`
  - snapshot from agent ownership at call time
- `agent_resource_scope`
  - snapshot from agent resource scope at call time
- `tenant_publication_id`
  - nullable for non-user calls
- `publication_*_snapshot`
  - immutable snapshot of publication state used to authorize the call

Implementation note:

Existing `tenant_id`, `user_id`, and `user_type` can either be retained as legacy aliases or replaced by the new names after the refactor. Since this is pre-production, replacing them directly is acceptable if the migration is done in one pass.

## Final billing rule

Billing always belongs to the consuming tenant, not the owner of the agent.

Examples:

- platform-owned shared agent used by tenant A user
  - billed to tenant A
- platform-owned shared agent used by tenant A admin
  - billed to tenant A
- tenant-owned agent used by the same tenant's user
  - billed to that tenant
- platform internal admin-only agent
  - not part of tenant billing

## Runtime Visibility Rules

### Platform admin

Platform admin visibility is based on agent ownership and distribution mode only.

### Tenant admin

Tenant admin can use:

- tenant-owned agents of the current tenant
- platform agents distributed to the current tenant

Tenant admin use does not depend on tenant-user publication.

### Tenant user

Tenant user can use only agents that satisfy both:

1. the agent is available to the tenant
2. the tenant has published the agent to tenant users

This is the key separation required by the business.

## Legacy to New Mapping

### Agent mapping

> **SUPERSEDED** — The mapping below used legacy scope values and columns.
> Current model uses five `ResourceScopeEnum` values + `owner_tenant_id` + RTA.
> See `.cursorrules` for the canonical specification.

- `scope = admin_only` → platform-owned, admin-side only
- `scope = global_shared` → platform-owned, visible everywhere
- `scope = all_tenants` (platform-owned) → visible to all tenants
- `scope = admin_and_selected_tenants` → platform-owned, admin + assigned tenants via RTA
- `scope = selected_tenants` → visible only to assigned tenants via RTA
- `scope = all_tenants` (tenant-owned) → tenant's own resource
  - `owner_tenant_id = X`

### target_audience mapping

`target_audience` is not kept.

It is used only once during migration to infer old endpoint visibility, then removed.

### AgentAccess mapping

If an `AgentAccess` record currently controls tenant-user access:

- create or update `TenantAgentPublication`
- move the tenant-user related rules there

If an `AgentAccess` record currently controls tenant-admin or platform-admin role restrictions:

- keep those fields only if they are still needed after the new visibility design

## Required Backend Refactor

### Remove

- `UsageStat`
- `UsageStatRepository`
- `MeteringService`
- `admin/ai_usage.py` old stats endpoints
- `tenant/ai_usage.py` old stats endpoints

### Add or replace

- agent ownership and distribution fields
- `TenantAgentPublication`
- unified `AgentVisibilityPolicyService`
- `AICallLog` attribution snapshot fields
- analytics queries built directly on `AICallLog`

### Centralize access checks

All runtime access checks must be moved to one policy service:

- `can_platform_admin_access_agent(...)`
- `can_tenant_admin_access_agent(...)`
- `can_tenant_user_access_agent(...)`
- `list_agents_visible_to_tenant(...)`
- `list_agents_published_to_tenant_users(...)`

The following paths must stop doing custom visibility logic:

- tenant agent repository
- user agent repository logic
- agent chat entry points
- agent router service

## Required Frontend Refactor

### Admin side

Admin manages:

- internal only
- available to all tenants
- available to assigned tenants

Admin no longer manages tenant-user publication semantics.

Remove:

- old audience semantics from admin agent forms

### Tenant side

Tenant manages:

- its own agents
- visibility of distributed platform agents
- publication of available agents to tenant users

Add:

- dedicated "publish to users" management UI

### User side

User sees only tenant-published agents.

User UI must not depend on old `target_audience` semantics.

## Analytics Replacement

After deleting `ai_usage_stats`, analytics must query `AICallLog` directly.

### Admin analytics should support

- tenant summary
- model summary
- provider summary
- call trend
- token trend
- tenant ranking
- success and failure rate

### Tenant analytics should support

- tenant summary
- tenant user summary
- model distribution
- agent ranking
- cost trend

### Billing support should support

- export by tenant and billing period
- grouping by agent owner type
- grouping by agent
- grouping by access channel
- grouping by actor user

## Migration Strategy

Because the project is pre-production, use a one-shot destructive migration.

Recommended sequence:

1. add new agent ownership and distribution fields
2. add `TenantAgentPublication`
3. add new `AICallLog` attribution fields
4. migrate existing agent and access data into the new structure
5. switch runtime services and APIs to the new policy model
6. switch analytics pages to query `AICallLog`
7. remove old usage stats table and code
8. remove legacy `target_audience` path
9. remove old runtime use of overloaded `scope`

## Out of Scope

This plan does not cover:

- pricing formula design
- invoice generation
- tax logic
- external payment provider integration

It only defines the domain model and billing-grade usage attribution foundation.

## Acceptance Criteria

- tenant user usage is always attributable to a tenant
- tenant user usage is always attributable to an agent
- historical usage does not change after later publication or assignment changes
- user access depends on tenant publication, not on platform audience flags
- old `ai_usage_stats` path is fully removed
- admin and tenant analytics no longer depend on `UsageStat`
- platform-to-tenant distribution and tenant-to-user publication are separate concepts in code and UI
