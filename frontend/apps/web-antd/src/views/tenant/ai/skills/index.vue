<script lang="ts" setup>
/**
 * 租户端技能管理列表页面
 */
import type { SkillInfo } from '#/api/tenant/skills';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Modal, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  deleteSkillApi,
  getSkillListApi,
  testSkillApi,
} from '#/api/tenant/skills';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  getSkillTypeColor,
  getSkillTypeIcon,
  getSkillTypeText,
  loadSkillTypes,
  useColumns,
  useGridFormSchema,
} from './data';
import SkillForm from './modules/SkillForm.vue';

defineOptions({ name: 'TenantSkillList' });

loadSkillTypes();

const skillFormRef = ref<InstanceType<typeof SkillForm>>();

function onEdit(row: SkillInfo) {
  skillFormRef.value?.openEdit(row);
}

async function onTest(row: SkillInfo) {
  try {
    const res = await testSkillApi(row.id);
    Modal[res.success ? 'success' : 'error']({
      title: row.name,
      content: res.message,
    });
  } catch {
    Modal.error({
      title: row.name,
      content: $t('tenant.ai.skill.testFailed'),
    });
  }
}

const { Grid, onRefresh } = useCrudPage<SkillInfo>({
  api: {
    list: getSkillListApi,
    delete: deleteSkillApi,
    resource: '/tenant/ai/skills',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: SkillForm,
  i18nPrefix: 'tenant.ai.skill',
  nameField: 'name',
  defaultSort: '-created_at',
  recycleBin: true,
  customActions: {
    edit: onEdit,
    test: onTest,
  },
});

function onFormSuccess() {
  onRefresh();
}
</script>

<template>
  <Page
    auto-content-height
    :description="$t('tenant.ai.skill.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 表单抽屉 -->
    <SkillForm ref="skillFormRef" @success="onFormSuccess" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 左侧工具栏：创建按钮 -->
        <template #toolbar-actions>
          <Button
            v-access:code="['skill:create']"
            type="primary"
            @click="skillFormRef?.openNew()"
          >
            <template #icon>
              <IconifyIcon icon="lucide:plus" class="size-4" />
            </template>
            {{ $t('tenant.ai.skill.create') }}
          </Button>
        </template>

        <!-- 技能名称列 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-1.5">
            <IconifyIcon
              :icon="getSkillTypeIcon(row.type)"
              class="size-3.5 text-muted-foreground"
            />
            <span class="font-medium">{{ row.name }}</span>
          </div>
        </template>

        <!-- 类型列 -->
        <template #type_cell="{ row }">
          <Tag :color="getSkillTypeColor(row.type)">
            {{ getSkillTypeText(row.type) }}
          </Tag>
        </template>

        <!-- 描述列 -->
        <template #description_cell="{ row }">
          <Tooltip v-if="row.description" :title="row.description">
            <span class="line-clamp-1 text-muted-foreground">
              {{ row.description }}
            </span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 启用状态列 -->
        <template #isActive_cell="{ row }">
          <Tag :color="row.is_active ? 'success' : 'default'">
            {{ row.is_active ? $t('common.enabled') : $t('common.disabled') }}
          </Tag>
        </template>

        <!-- 超时列 -->
        <template #timeout_cell="{ row }">
          <span class="text-muted-foreground">{{ row.timeout }}s</span>
        </template>

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <Tooltip :title="formatDate(row.created_at)">
            <span class="text-muted-foreground">
              {{ formatDate(row.created_at) }}
            </span>
          </Tooltip>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
