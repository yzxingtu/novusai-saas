<script lang="ts" setup>
/**
 * 代码生成器配置列表页 / Codegen config list page
 *
 * DEBUG 模式下可用 / Available in DEBUG mode only
 * 双入口：从数据库导入 / 手动创建
 */
import type { CodegenConfigInfo } from '#/api/admin/codegen';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';

import { Button, Card, message, Modal } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  createCodegenConfigApi,
  deleteCodegenConfigApi,
  deleteCodegenRollbackApi,
  downloadCodegenZipApi,
  duplicateCodegenConfigApi,
  getCodegenConfigListApi,
  postCodegenGenerateApi,
} from '#/api/admin/codegen';
import { $t } from '#/locales';

import DbTableImportModal from './modules/DbTableImportModal.vue';
import PresetSelectModal from './modules/PresetSelectModal.vue';
import { useColumns, useGridFormSchema } from './data';

defineOptions({ name: 'AdminSystemCodegenList' });

const router = useRouter();
const dbImportVisible = ref(false);
const presetSelectVisible = ref(false);

async function onActionClick(params: { code: string; row: CodegenConfigInfo }) {
  const { code, row } = params;
  if (!row?.id) return;
  switch (code) {
    case 'edit': {
      router.push(`/admin/system/codegen/${row.id}/edit`);
      break;
    }
    case 'generate': {
      Modal.confirm({
        title: $t('admin.system.codegen.confirm.generate', { name: row.name }),
        onOk: async () => {
          try {
            const result = await postCodegenGenerateApi({
              config_id: row.id,
              force: false,
            });
            if ((result as { success?: boolean }).success !== false) {
              message.success($t('admin.system.codegen.messages.generateSuccess'));
              gridReload();
            } else {
              const errs = (result as { errors?: string[] }).errors;
              message.error(errs?.length ? errs.join('; ') : $t('common.failed'));
              gridReload();
            }
          } catch {
            message.error($t('common.failed'));
            gridReload();
          }
        },
      });
      break;
    }
    case 'download': {
      try {
        await downloadCodegenZipApi(row.id);
        message.success($t('admin.system.codegen.messages.downloadSuccess'));
      } catch {
        message.error($t('admin.system.codegen.messages.downloadFail'));
      }
      break;
    }
    case 'duplicate': {
      try {
        await duplicateCodegenConfigApi(row.id);
        message.success($t('admin.system.codegen.messages.duplicateSuccess'));
        gridReload();
      } catch {
        message.error($t('common.failed'));
      }
      break;
    }
    case 'rollback': {
      Modal.confirm({
        okType: 'danger',
        title: $t('admin.system.codegen.confirm.rollback', { name: row.name }),
        onOk: async () => {
          try {
            const result = await deleteCodegenRollbackApi(row.id, { force: true });
            if ((result as { success?: boolean }).success !== false) {
              message.success($t('admin.system.codegen.messages.rollbackSuccess'));
              gridReload();
            } else {
              const errs = (result as { errors?: string[] }).errors;
              message.error(errs?.length ? errs.join('; ') : $t('common.failed'));
              gridReload();
            }
          } catch {
            message.error($t('common.failed'));
            gridReload();
          }
        },
      });
      break;
    }
    case 'delete': {
      Modal.confirm({
        okType: 'danger',
        title: $t('admin.system.codegen.confirm.delete', { name: row.name }),
        onOk: async () => {
          try {
            await deleteCodegenConfigApi(row.id);
            gridReload();
          } catch {
            message.error($t('common.failed'));
          }
        },
      });
      break;
    }
  }
}

function openDbImport() {
  dbImportVisible.value = true;
}

function openPresetSelect() {
  presetSelectVisible.value = true;
}

function onPresetSelect(presetId: string | null) {
  presetSelectVisible.value = false;
  const query = presetId ? { preset: presetId } : {};
  router.replace({ path: '/admin/system/codegen/new', query });
}

async function onDbImportApplied(patch: Record<string, unknown>) {
  try {
    const resource = (patch.resource as string) || 'unnamed';
    const moduleVal = (patch.module as string) || 'system';
    const displayName = (patch.display_name as string) || resource;
    const displayNameEn = (patch.display_name_en as string) || resource;
    const name = (patch.name as string) || displayName || $t('admin.system.codegen.unnamed');

    const res = await createCodegenConfigApi({
      name,
      resource,
      module: moduleVal,
      display_name: displayName,
      display_name_en: displayNameEn,
      config_json: patch,
    });
    dbImportVisible.value = false;
    message.success($t('shared.common.success'));
    router.replace(`/admin/system/codegen/${res.id}/edit`);
  } catch {
    message.error($t('common.failed'));
  }
}

const { Grid, onRefresh: gridReload, gridApi } = useCrudPage<CodegenConfigInfo>({
  api: {
    list: getCodegenConfigListApi,
    resource: '/admin/codegen/configs',
    delete: deleteCodegenConfigApi,
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.system.codegen',
  defaultSort: '-created_at',
  toolbar: { custom: true, export: true, refresh: true, search: true, zoom: false },
  customActions: {
    edit: (row) => onActionClick({ code: 'edit', row }),
    generate: (row) => onActionClick({ code: 'generate', row }),
    download: (row) => onActionClick({ code: 'download', row }),
    duplicate: (row) => onActionClick({ code: 'duplicate', row }),
    rollback: (row) => onActionClick({ code: 'rollback', row }),
    delete: (row) => onActionClick({ code: 'delete', row }),
  },
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.system.codegen.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <div class="flex items-center justify-between">
      <span class="text-muted-foreground text-sm">
        {{ $t('admin.system.codegen.debugHint') }}
      </span>
      <div class="flex gap-2">
        <Button @click="openDbImport">
          <IconifyIcon icon="lucide:database" class="mr-1 size-4" />
          {{ $t('admin.system.codegen.importFromDb') }}
        </Button>
        <Button type="primary" @click="openPresetSelect">
          <IconifyIcon icon="lucide:plus" class="mr-1 size-4" />
          {{ $t('admin.system.codegen.create') }}
        </Button>
      </div>
    </div>
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid />
    </Card>

    <DbTableImportModal
      v-model:open="dbImportVisible"
      @applied="onDbImportApplied"
    />
    <PresetSelectModal
      v-model:open="presetSelectVisible"
      @select="onPresetSelect"
    />
  </Page>
</template>
