<script lang="ts" setup>
import { select } from '#/adapter/form';
import {
  clearRecycleBinModuleApi,
  getRecycleBinListApi,
  getRecycleBinModulesApi,
  getRecycleBinSummaryApi,
  permanentDeleteRecycleBinItemApi,
  restoreRecycleBinItemApi,
  triggerRecycleBinCleanupApi,
} from '#/api/admin/recycle-bin';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';
import SharedRecycleBinPage from '#/views/_shared/recycle-bin/recycle-bin-page.vue';

import { useAdminRecycleBinAdapters } from './adapters';

defineOptions({ name: 'AdminSystemRecycleBin' });

const adapters = useAdminRecycleBinAdapters();

function tenantFieldSchema(fieldName: string) {
  return select(`filter[${fieldName}]`, $t('admin.system.recycleBin.tenant'), {
    api: getTenantSelectApi,
    placeholder: $t('admin.system.recycleBin.allTenants'),
  });
}
</script>

<template>
  <SharedRecycleBinPage
    :api="{
      clearModule: clearRecycleBinModuleApi,
      getList: getRecycleBinListApi,
      getModules: getRecycleBinModulesApi,
      getSummary: getRecycleBinSummaryApi,
      permanentDelete: permanentDeleteRecycleBinItemApi,
      restore: restoreRecycleBinItemApi,
      triggerCleanup: triggerRecycleBinCleanupApi,
    }"
    i18n-prefix="admin.system.recycleBin"
    :module-adapters="adapters"
    :show-cleanup="true"
    :tenant-field-schema="tenantFieldSchema"
  />
</template>
