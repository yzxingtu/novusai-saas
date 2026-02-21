<script lang="ts" setup>
/**
 * 租户端智能体管理列表页面
 *
 * 卡片网格布局，与管理端风格一致。
 * 包含：CRUD、发布、版本历史、访问权限、测试对话。
 */
import type { AgentListItem } from '#/api/tenant/agents';

defineOptions({ name: 'TenantAgentList' });

import { computed, onMounted, ref, watch } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Drawer,
  Dropdown,
  Empty,
  Input,
  Menu,
  MenuItem,
  message,
  Modal,
  Pagination,
  Popconfirm,
  Select,
  SelectOption,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  deleteAgentApi,
  getAgentListApi,
  getAgentRecycleBinApi,
  getAgentRecycleBinCountApi,
  permanentDeleteAgentApi,
  publishAgentApi,
  restoreAgentApi,
} from '#/api/tenant/agents';
import { $t } from '#/locales';
import { formatRelativeTime } from '#/utils/common';

import {
  getExecutionModeText,
  getStatusText,
} from './data';
import AgentForm from './modules/AgentForm.vue';
import VersionHistory from './modules/VersionHistory.vue';

// ============================================================
// Refs & Drawers
// ============================================================

const agentFormRef = ref<InstanceType<typeof AgentForm>>();
const agents = ref<AgentListItem[]>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(12);
const searchKeyword = ref('');
const filterStatus = ref<string>();

const [VersionHistoryDrawer, versionHistoryApi] = useVbenDrawer({
  connectedComponent: VersionHistory,
});

// 发布弹窗
const publishModalOpen = ref(false);
const publishChangeLog = ref('');
const publishLoading = ref(false);
let publishAgentId = 0;

// 回收站
const recycleBinVisible = ref(false);
const recycleBinLoading = ref(false);
const recycleBinItems = ref<AgentListItem[]>([]);
const recycleBinCount = ref(0);

// ============================================================
// Data fetching
// ============================================================

async function fetchAgents() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {
      'page[number]': page.value,
      'page[size]': pageSize.value,
      sort: '-created_at',
    };
    if (searchKeyword.value) {
      params['filter[name][ilike]'] = searchKeyword.value;
    }
    if (filterStatus.value) {
      params['filter[status][eq]'] = filterStatus.value;
    }
    const res = await getAgentListApi(params);
    agents.value = res.items || [];
    total.value = res.total || 0;
  } catch {
    agents.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

onMounted(fetchAgents);
watch([page, pageSize], fetchAgents);

// ============================================================
// Search & Filter
// ============================================================

let searchTimer: ReturnType<typeof setTimeout>;
function onSearchInput(val: string) {
  searchKeyword.value = val;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    page.value = 1;
    fetchAgents();
  }, 350);
}

function onFilterChange() {
  page.value = 1;
  fetchAgents();
}

function onClearFilters() {
  searchKeyword.value = '';
  filterStatus.value = undefined;
  page.value = 1;
  fetchAgents();
}

const hasActiveFilters = computed(
  () => !!searchKeyword.value || !!filterStatus.value,
);

// ============================================================
// Actions
// ============================================================

function onDelete(agent: AgentListItem) {
  if (agent.is_system) return;
  Modal.confirm({
    title: $t('ui.actionMessage.deleteConfirm', { name: agent.name }),
    content: $t('ui.actionMessage.deleteConfirmContent'),
    okType: 'danger',
    async onOk() {
      try {
        await deleteAgentApi(agent.id);
        message.success($t('ui.actionMessage.deleteSuccess'));
        await fetchAgents();
      } catch {
        // handled by interceptor
      }
    },
  });
}

function onPublish(agent: AgentListItem) {
  publishAgentId = agent.id;
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
    await fetchAgents();
  } catch {
    // handled by interceptor
  } finally {
    publishLoading.value = false;
  }
}

function onVersions(agent: AgentListItem) {
  versionHistoryApi.setData({
    id: agent.id,
    publishedVersion: agent.published_version ?? null,
  });
  versionHistoryApi.open();
}


// ============================================================
// Helpers
// ============================================================

function getStatusDotClass(status: string): string {
  switch (status) {
    case 'published': return 'bg-green-500';
    case 'disabled': return 'bg-red-400';
    default: return 'bg-gray-400';
  }
}

function getExecutionModeIcon(mode: string): string {
  switch (mode) {
    case 'conversation': return 'lucide:message-circle';
    case 'task': return 'lucide:list-checks';
    case 'batch': return 'lucide:layers';
    case 'api': return 'lucide:code';
    default: return 'lucide:bot';
  }
}

const stats = computed(() => ({
  total: total.value,
  published: agents.value.filter((a) => a.status === 'published').length,
  system: agents.value.filter((a) => a.is_system).length,
}));

// ============================================================
// Recycle Bin
// ============================================================

async function loadRecycleBinCount() {
  try {
    const res = await getAgentRecycleBinCountApi();
    recycleBinCount.value = res.count;
  } catch {
    recycleBinCount.value = 0;
  }
}

async function openRecycleBin() {
  recycleBinVisible.value = true;
  await loadRecycleBinItems();
}

async function loadRecycleBinItems() {
  recycleBinLoading.value = true;
  try {
    const res = await getAgentRecycleBinApi({ 'page[size]': 100 });
    recycleBinItems.value = res.items;
  } catch {
    recycleBinItems.value = [];
  } finally {
    recycleBinLoading.value = false;
  }
}

async function onRestoreAgent(id: number) {
  try {
    await restoreAgentApi(id);
    message.success($t('common.recycleBin.restoreSuccess'));
    await loadRecycleBinItems();
    await loadRecycleBinCount();
    await fetchAgents();
  } catch {
    // handled by interceptor
  }
}

async function onPermanentDeleteAgent(id: number) {
  try {
    await permanentDeleteAgentApi(id);
    message.success($t('common.deleteSuccess'));
    await loadRecycleBinItems();
    await loadRecycleBinCount();
  } catch {
    // handled by interceptor
  }
}

const recycleBinColumns = computed(() => [
  { title: $t('tenant.ai.agent.name'), dataIndex: 'name', key: 'name' },
  { title: $t('tenant.ai.agent.status'), dataIndex: 'status', key: 'status', width: 100 },
  { title: $t('common.recycleBin.deletedAt'), dataIndex: 'deleted_at', key: 'deleted_at', width: 160 },
  { title: $t('common.operation'), key: 'action', width: 180, align: 'center' as const },
]);

onMounted(() => {
  loadRecycleBinCount();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- Drawers -->
    <AgentForm ref="agentFormRef" @success="fetchAgents" />
    <VersionHistoryDrawer @success="fetchAgents" />

    <!-- Publish Modal -->
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

    <!-- ==================== Top Bar ==================== -->
    <div class="flex flex-wrap items-center gap-3">
      <Input
        :value="searchKeyword"
        :placeholder="$t('tenant.ai.agent.placeholder.searchName')"
        allow-clear
        class="!w-64"
        @update:value="onSearchInput"
      >
        <template #prefix>
          <IconifyIcon icon="lucide:search" class="size-4 text-muted-foreground" />
        </template>
      </Input>

      <Select
        v-model:value="filterStatus"
        :placeholder="$t('tenant.ai.agent.status')"
        allow-clear
        class="!w-32"
        @change="onFilterChange"
      >
        <SelectOption value="published">
          {{ $t('tenant.ai.agent.status_options.published') }}
        </SelectOption>
        <SelectOption value="disabled">
          {{ $t('tenant.ai.agent.status_options.disabled') }}
        </SelectOption>
        <SelectOption value="draft">
          {{ $t('tenant.ai.agent.status_options.draft') }}
        </SelectOption>
      </Select>

      <Button
        v-if="hasActiveFilters"
        type="link"
        size="small"
        @click="onClearFilters"
      >
        {{ $t('common.reset') }}
      </Button>

      <div class="flex-1" />

      <div class="hidden items-center gap-4 text-xs text-muted-foreground md:flex">
        <span>{{ $t('common.total') }} {{ stats.total }}</span>
        <span class="flex items-center gap-1">
          <span class="inline-block size-2 rounded-full bg-green-500" />
          {{ stats.published }}
        </span>
      </div>

      <!-- Recycle bin -->
      <Tooltip :title="$t('common.recycleBin.title')">
        <Badge :count="recycleBinCount" :offset="[-2, 2]" size="small">
          <Button @click="openRecycleBin">
            <template #icon>
              <IconifyIcon icon="lucide:trash-2" class="size-4" />
            </template>
          </Button>
        </Badge>
      </Tooltip>

      <Button
        v-access:code="['agent:create']"
        type="primary"
        @click="agentFormRef?.openNew()"
      >
        <template #icon>
          <IconifyIcon icon="lucide:plus" class="size-4" />
        </template>
        {{ $t('tenant.ai.agent.create') }}
      </Button>
    </div>

    <!-- ==================== Card Grid ==================== -->
    <Spin :spinning="loading">
      <div
        v-if="agents.length > 0"
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
      >
        <div
          v-for="agent in agents"
          :key="agent.id"
          class="group relative rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-primary/30 hover:shadow-md"
        >
          <!-- Header -->
          <div class="flex items-start gap-3.5">
            <div
              class="flex size-11 shrink-0 items-center justify-center rounded-xl text-base font-semibold"
              :class="agent.is_system
                ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                : 'bg-primary/10 text-primary'"
            >
              <img
                v-if="agent.avatar"
                :src="agent.avatar"
                :alt="agent.name"
                class="size-full rounded-xl object-cover"
              />
              <IconifyIcon
                v-else-if="agent.is_system"
                icon="lucide:shield-check"
                class="size-5"
              />
              <span v-else>{{ agent.name?.charAt(0)?.toUpperCase() || '?' }}</span>
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <h3 class="truncate text-sm font-semibold text-foreground">
                  {{ agent.name }}
                </h3>
                <Tag
                  v-if="agent.is_system"
                  color="purple"
                  class="!mr-0 shrink-0 !text-[10px] !leading-4"
                  style="padding: 0 5px"
                >
                  {{ $t('tenant.ai.agent.system') }}
                </Tag>
              </div>
              <div class="mt-1 flex items-center gap-1.5">
                <span
                  class="inline-block size-2 rounded-full"
                  :class="getStatusDotClass(agent.status)"
                />
                <span class="text-xs text-muted-foreground">
                  {{ getStatusText(agent.status) }}
                </span>
              </div>
            </div>

            <!-- Dropdown -->
            <Dropdown
              :trigger="['click']"
              placement="bottomRight"
              class="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
            >
              <button
                class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <IconifyIcon icon="lucide:more-vertical" class="size-4" />
              </button>
              <template #overlay>
                <Menu>
                  <MenuItem key="edit" @click="agentFormRef?.openEdit(agent)">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:pencil" class="size-4" />
                      <span>{{ $t('common.edit') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem
                    v-if="!agent.is_system && agent.status === 'draft'"
                    key="publish"
                    @click="onPublish(agent)"
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:rocket" class="size-4 text-success" />
                      <span>{{ $t('tenant.ai.agent.actions.publish') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem key="versions" @click="onVersions(agent)">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:history" class="size-4" />
                      <span>{{ $t('tenant.ai.agent.actions.versions') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem
                    v-if="!agent.is_system"
                    key="delete"
                    class="!text-destructive"
                    @click="onDelete(agent)"
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:trash-2" class="size-4" />
                      <span>{{ $t('common.delete') }}</span>
                    </div>
                  </MenuItem>
                </Menu>
              </template>
            </Dropdown>
          </div>

          <!-- Description -->
          <p
            v-if="agent.description"
            class="mt-3 line-clamp-2 text-xs leading-relaxed text-muted-foreground"
          >
            {{ agent.description }}
          </p>
          <p v-else class="mt-3 text-xs italic text-muted-foreground/50">
            {{ $t('tenant.ai.agent.noDescription') }}
          </p>

          <!-- Metadata chips -->
          <div class="mt-4 flex flex-wrap items-center gap-2">
            <Tooltip v-if="agent.model_name" :title="$t('tenant.ai.agent.modelName')">
              <div
                class="flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
              >
                <IconifyIcon icon="lucide:brain" class="size-3" />
                <span>{{ agent.model_name }}</span>
              </div>
            </Tooltip>

            <Tooltip :title="$t('tenant.ai.agent.executionMode')">
              <div
                class="flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
              >
                <IconifyIcon :icon="getExecutionModeIcon(agent.execution_mode)" class="size-3" />
                <span>{{ getExecutionModeText(agent.execution_mode) }}</span>
              </div>
            </Tooltip>

            <Tag
              v-for="pkg in (agent.skill_packages || []).slice(0, 3)"
              :key="pkg.id"
              color="cyan"
              class="!mr-0 !text-[11px]"
              style="padding: 0 6px; line-height: 20px"
            >
              {{ pkg.name }}
            </Tag>
            <Tooltip
              v-if="agent.skill_packages && agent.skill_packages.length > 3"
              :title="agent.skill_packages.slice(3).map((p: { name: string }) => p.name).join(', ')"
            >
              <Tag color="cyan" class="!mr-0 !text-[11px]" style="padding: 0 6px; line-height: 20px">
                +{{ agent.skill_packages.length - 3 }}
              </Tag>
            </Tooltip>

            <span
              v-if="agent.published_version"
              class="rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
            >
              v{{ agent.published_version }}
            </span>
          </div>

          <!-- Footer -->
          <div
            class="mt-4 flex items-center justify-between border-t border-border/50 pt-3 text-[11px] text-muted-foreground"
          >
            <Tooltip :title="agent.created_at">
              <span>{{ formatRelativeTime(agent.created_at) }}</span>
            </Tooltip>
            <button
              class="flex items-center gap-1 rounded-md px-2 py-1 text-primary transition-colors hover:bg-primary/10 md:opacity-0 md:group-hover:opacity-100"
              @click="agentFormRef?.openEdit(agent)"
            >
              <IconifyIcon icon="lucide:pencil" class="size-3" />
              <span>{{ $t('common.edit') }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="!loading" class="flex min-h-[300px] items-center justify-center">
        <Empty :description="$t('common.noData')">
          <Button
            v-access:code="['agent:create']"
            type="primary"
            @click="agentFormRef?.openNew()"
          >
            <template #icon>
              <IconifyIcon icon="lucide:plus" class="size-4" />
            </template>
            {{ $t('tenant.ai.agent.create') }}
          </Button>
        </Empty>
      </div>
    </Spin>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="flex justify-end">
      <Pagination
        v-model:current="page"
        v-model:pageSize="pageSize"
        :total="total"
        :page-size-options="['12', '24', '48']"
        show-size-changer
        show-quick-jumper
        size="small"
      />
    </div>

    <!-- ==================== Recycle Bin Drawer ==================== -->
    <Drawer
      v-model:open="recycleBinVisible"
      :title="$t('common.recycleBin.title')"
      width="600"
      :destroy-on-close="true"
    >
      <Table
        :columns="recycleBinColumns"
        :data-source="recycleBinItems"
        :loading="recycleBinLoading"
        :pagination="false"
        row-key="id"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'deleted_at'">
            <span class="text-xs text-muted-foreground">
              {{ formatRelativeTime(record.deleted_at) }}
            </span>
          </template>
          <template v-if="column.key === 'action'">
            <Space>
              <Button
                type="link"
                size="small"
                @click="onRestoreAgent(record.id)"
              >
                {{ $t('common.recycleBin.restore') }}
              </Button>
              <Popconfirm
                :title="$t('common.recycleBin.permanentDeleteConfirm')"
                @confirm="onPermanentDeleteAgent(record.id)"
              >
                <Button type="link" size="small" danger>
                  {{ $t('common.recycleBin.permanentDelete') }}
                </Button>
              </Popconfirm>
            </Space>
          </template>
        </template>
        <template #emptyText>
          <Empty :description="$t('common.recycleBin.empty')" />
        </template>
      </Table>
    </Drawer>
  </Page>
</template>
