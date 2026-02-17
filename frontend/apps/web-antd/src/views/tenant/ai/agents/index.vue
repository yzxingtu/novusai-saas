<script lang="ts" setup>
/**
 * 租户端智能体管理列表页面
 */
import type { AgentListItem } from '#/api/tenant/agents';

defineOptions({ name: 'TenantAgentList' });

import { ref } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import { Card, Input, message, Modal, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';

import QuickStartGuide from '#/components/business/quick-start-guide/QuickStartGuide.vue';
import {
  deleteAgentApi,
  getAgentListApi,
  publishAgentApi,
} from '#/api/tenant/agents';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  getExecutionModeColor,
  getExecutionModeText,
  getStatusColor,
  getStatusText,
  getVisibilityColor,
  getVisibilityText,
  useColumns,
  useGridFormSchema,
} from './data';
import AccessConfigDrawer from './modules/AccessConfigDrawer.vue';
import AgentForm from './modules/AgentForm.vue';
import AgentTestDrawer from './modules/AgentTestDrawer.vue';
import VersionHistory from './modules/VersionHistory.vue';

const agentFormRef = ref<InstanceType<typeof AgentForm>>();

// 测试对话抽屉
const [TestDrawer, testDrawerApi] = useVbenDrawer({
  connectedComponent: AgentTestDrawer,
});

// 访问权限抽屉
const [AccessDrawer, accessDrawerApi] = useVbenDrawer({
  connectedComponent: AccessConfigDrawer,
});

// 版本历史抽屉
const [VersionHistoryDrawer, versionHistoryApi] = useVbenDrawer({
  connectedComponent: VersionHistory,
});

function onEdit(row: AgentListItem) {
  agentFormRef.value?.openEdit(row);
}

// 发布弹窗状态
const publishModalOpen = ref(false);
const publishChangeLog = ref('');
const publishLoading = ref(false);
let publishAgentId = 0;

/** 发布：打开 Modal 输入 change_log */
function onPublish(row: AgentListItem) {
  publishAgentId = row.id;
  publishChangeLog.value = '';
  publishModalOpen.value = true;
}

async function onPublishConfirm() {
  publishLoading.value = true;
  try {
    await publishAgentApi(publishAgentId, {
      change_log: publishChangeLog.value || null,
    });
    message.success($t('tenant.ai.agent.messages.publishSuccess'));
    publishModalOpen.value = false;
    gridReload();
  } catch {
    // error handled by global interceptor
  } finally {
    publishLoading.value = false;
  }
}

/** 访问权限 */
function onAccess(row: AgentListItem) {
  accessDrawerApi
    .setData({
      id: row.id,
      name: row.name,
    })
    .open();
}

/** 测试对话 */
function onTest(row: AgentListItem) {
  testDrawerApi
    .setData({
      id: row.id,
      name: row.name,
      status: row.status,
    })
    .open();
}

/** 查看版本历史 */
function onVersions(row: AgentListItem) {
  versionHistoryApi
    .setData({
      id: row.id,
      publishedVersion: row.published_version ?? null,
    })
    .open();
}

const { Grid, onRefresh: gridReload } = useCrudPage<AgentListItem>({
  api: {
    list: getAgentListApi,
    delete: deleteAgentApi,
    resource: '/tenant/ai/agents',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: AgentForm,
  i18nPrefix: 'tenant.ai.agent',
  nameField: 'name',
  defaultSort: '-created_at',
  recycleBin: true,
  customActions: {
    access: onAccess,
    test: onTest,
    publish: onPublish,
    edit: onEdit,
    versions: onVersions,
  },
});

function onFormSuccess() {
  gridReload();
}

function onVersionSuccess() {
  gridReload();
}
</script>

<template>
  <Page auto-content-height :description="$t('tenant.ai.agent.pageDesc')" content-class="flex flex-col gap-4">
    <QuickStartGuide
      storage-key="tenant-ai-guide-dismissed"
      i18n-prefix="tenant.ai"
      :steps="[
        { key: 'step1', icon: 'lucide:bot', color: 'text-primary', bg: 'bg-primary/10', link: '/tenant/ai/agents' },
        { key: 'step2', icon: 'lucide:sparkles', color: 'text-purple-600', bg: 'bg-purple-500/10', link: '/tenant/ai/skills' },
        { key: 'step3', icon: 'lucide:rocket', color: 'text-amber-600', bg: 'bg-amber-500/10', link: '/tenant/ai/agents' },
        { key: 'step4', icon: 'lucide:message-circle', color: 'text-success', bg: 'bg-success/10', link: '/tenant/ai/chat' },
      ]"
    />
    <!-- 表单抽屉 -->
    <AgentForm ref="agentFormRef" @success="onFormSuccess" />
    <!-- 访问权限抽屉 -->
    <AccessDrawer @success="onFormSuccess" />
    <!-- 测试对话抽屉 -->
    <TestDrawer />
    <!-- 版本历史抽屉 -->
    <VersionHistoryDrawer @success="onVersionSuccess" />

    <!-- 发布弹窗 -->
    <Modal
      v-model:open="publishModalOpen"
      :title="$t('tenant.ai.agent.version.publishTitle')"
      :confirm-loading="publishLoading"
      @ok="onPublishConfirm"
    >
      <p class="mb-2 text-muted-foreground">
        {{ $t('tenant.ai.agent.version.publishDesc') }}
      </p>
      <Input.TextArea
        v-model:value="publishChangeLog"
        :placeholder="$t('tenant.ai.agent.version.changeLogPlaceholder')"
        :rows="3"
        :maxlength="2000"
        show-count
      />
    </Modal>

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Card
            v-access:code="['agent:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="agentFormRef?.openNew()"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{
                $t('tenant.ai.agent.create')
              }}</span>
            </div>
          </Card>
        </template>

        <!-- 名称列 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2.5">
            <div class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-sm font-medium text-primary">
              <img
                v-if="row.avatar"
                :src="row.avatar"
                :alt="row.name"
                class="size-full rounded-lg object-cover"
              />
              <span v-else>{{ row.name?.charAt(0)?.toUpperCase() || '?' }}</span>
            </div>
            <span class="font-medium text-foreground">{{ row.name }}</span>
            <Tag v-if="row.is_system" color="purple" class="ml-1" style="font-size: 10px; line-height: 16px; padding: 0 4px;">
              {{ $t('tenant.ai.agent.system') }}
            </Tag>
            <Tooltip v-if="row.welcome_message" :title="$t('tenant.ai.agent.hasWelcomeMessage')">
              <IconifyIcon icon="lucide:message-circle-heart" class="ml-1 size-3.5 text-primary/60" />
            </Tooltip>
          </div>
          <div
            v-if="row.description"
            class="mt-0.5 truncate text-xs text-muted-foreground"
          >
            {{ row.description }}
          </div>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag :color="getStatusColor(row.status)">
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <!-- 可见性列 -->
        <template #visibility_cell="{ row }">
          <Tag :color="getVisibilityColor(row.visibility)">
            {{ getVisibilityText(row.visibility) }}
          </Tag>
        </template>

        <!-- 执行模式列 -->
        <template #mode_cell="{ row }">
          <Tag :color="getExecutionModeColor(row.execution_mode)">
            {{ getExecutionModeText(row.execution_mode) }}
          </Tag>
        </template>

        <!-- 技能包列 -->
        <template #skill_count_cell="{ row }">
          <template v-if="row.skill_packages && row.skill_packages.length > 0">
            <Tag
              v-for="pkg in row.skill_packages.slice(0, 3)"
              :key="pkg.id"
              color="cyan"
              class="mr-1"
            >
              {{ pkg.name }}
            </Tag>
            <Tooltip v-if="row.skill_packages.length > 3" :title="row.skill_packages.slice(3).map((p: { name: string }) => p.name).join(', ')">
              <Tag color="cyan">+{{ row.skill_packages.length - 3 }}</Tag>
            </Tooltip>
          </template>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 模型列 -->
        <template #model_cell="{ row }">
          <span v-if="row.model_name" class="text-muted-foreground">
            {{ row.model_name }}
          </span>
          <span v-else class="text-muted-foreground">-</span>
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

        <!-- 创建时间列 -->
        <template #createdAt_cell="{ row }">
          <span class="text-muted-foreground">
            {{ formatDate(row.created_at) }}
          </span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
