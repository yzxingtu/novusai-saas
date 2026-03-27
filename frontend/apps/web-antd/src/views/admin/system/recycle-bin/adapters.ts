import type { RecycleBinModuleAdapter } from '#/views/_shared/recycle-bin/types';

import { $t } from '#/locales';
import { useGridFormSchema as useModelSearchSchema } from '#/views/admin/ai/models/data';
import { useGridFormSchema as useProviderSearchSchema } from '#/views/admin/ai/providers/data';
import { useGridFormSchema as usePeriodicTaskSearchSchema } from '#/views/admin/system/periodic-tasks/data';
import { useGridFormSchema as useTenantSearchSchema } from '#/views/admin/tenant/list/data';
import { useGridFormSchema as useTenantPlanSearchSchema } from '#/views/admin/tenant/plans/data';

export function useAdminRecycleBinAdapters(): Record<
  string,
  RecycleBinModuleAdapter
> {
  return {
    ai_models: {
      columns: () => [
        { field: 'name', minWidth: 180, title: $t('admin.ai.model.name') },
        { field: 'code', minWidth: 160, title: $t('admin.ai.model.code') },
        { field: 'type', title: $t('admin.ai.model.type'), width: 110 },
        {
          field: 'provider_name',
          minWidth: 150,
          title: $t('admin.ai.model.providerName'),
        },
        {
          field: 'context_window',
          title: $t('admin.ai.model.contextWindow'),
          width: 120,
        },
        {
          field: 'input_price_per_1k',
          title: $t('admin.ai.model.inputPrice'),
          width: 130,
        },
        { field: 'tier', title: $t('admin.ai.model.tier'), width: 110 },
        {
          align: 'center',
          field: 'is_active',
          title: $t('admin.ai.model.isActive'),
          width: 110,
        },
      ],
      searchSchema: useModelSearchSchema,
    },
    ai_providers: {
      columns: () => [
        { field: 'name', minWidth: 220, title: $t('admin.ai.provider.name') },
        { field: 'type', title: $t('admin.ai.provider.type'), width: 140 },
        { field: 'code', minWidth: 140, title: $t('admin.ai.provider.code') },
        {
          align: 'center',
          field: 'is_active',
          title: $t('admin.ai.provider.isActive'),
          width: 110,
        },
      ],
      searchSchema: useProviderSearchSchema,
    },
    periodic_tasks: {
      columns: () => [
        {
          field: 'name',
          minWidth: 220,
          title: $t('admin.system.periodicTask.name'),
        },
        {
          field: 'schedule_display',
          minWidth: 150,
          title: $t('admin.system.periodicTask.schedule'),
        },
        {
          align: 'center',
          field: 'is_active',
          title: $t('admin.system.periodicTask.isActive'),
          width: 100,
        },
        {
          field: 'last_run_at',
          minWidth: 150,
          title: $t('admin.system.periodicTask.runInfo'),
        },
        {
          field: 'task_path',
          minWidth: 220,
          title: $t('admin.system.periodicTask.taskPath'),
        },
      ],
      searchSchema: usePeriodicTaskSearchSchema,
    },
    tenant_plans: {
      columns: () => [
        { field: 'name', minWidth: 180, title: $t('admin.tenant.plan.name') },
        { field: 'code', minWidth: 140, title: $t('admin.tenant.plan.code') },
        { field: 'price', title: $t('admin.tenant.plan.price'), width: 120 },
        {
          field: 'billing_cycle',
          title: $t('admin.tenant.plan.billingCycle'),
          width: 120,
        },
        {
          align: 'center',
          field: 'is_active',
          title: $t('admin.tenant.plan.isActive'),
          width: 100,
        },
        {
          field: 'created_at',
          title: $t('admin.common.createdAt'),
          width: 150,
        },
      ],
      searchSchema: useTenantPlanSearchSchema,
    },
    tenants: {
      columns: () => [
        { field: 'name', minWidth: 200, title: $t('admin.tenant.name') },
        { field: 'code', minWidth: 140, title: $t('admin.tenant.code') },
        {
          field: 'contact_name',
          minWidth: 120,
          title: $t('admin.tenant.contactName'),
        },
        {
          field: 'contact_phone',
          minWidth: 140,
          title: $t('admin.tenant.contactPhone'),
        },
        {
          align: 'center',
          field: 'is_active',
          title: $t('admin.tenant.status'),
          width: 100,
        },
        {
          field: 'expires_at',
          title: $t('admin.tenant.expiresAt'),
          width: 150,
        },
        {
          field: 'created_at',
          title: $t('admin.tenant.createdAt'),
          width: 150,
        },
      ],
      searchSchema: useTenantSearchSchema,
    },
  };
}
