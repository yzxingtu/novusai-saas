<script lang="ts" setup>
/**
 * 智能体管理列表页面（平台端）
 *
 * 卡片网格布局，替代传统表格，提供更好的视觉层次和交互体验。
 */
import type { AIAgentInfo } from '#/api/admin/ai';

defineOptions({ name: 'AIAgentList' });

import { computed, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Dropdown,
  Empty,
  Input,
  Menu,
  MenuItem,
  message,
  Modal,
  Pagination,
  Select,
  SelectOption,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  deleteAIAgentApi,
  getAIAgentListApi,
  updateAIAgentStatusApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';
import { formatRelativeTime } from '#/utils/common';

import {
  getExecutionModeText,
  getScopeColor,
  getScopeOptions,
  getStatusText,
} from './data';
import AgentForm from './modules/form.vue';

// ============================================================
// Refs
// ============================================================

const agentFormRef = ref<InstanceType<typeof AgentForm>>();
const agents = ref<AIAgentInfo[]>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(12);
const searchKeyword = ref('');
const filterScope = ref<string>();
const filterStatus = ref<string>();

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
    if (filterScope.value) {
      params['filter[scope][eq]'] = filterScope.value;
    }
    if (filterStatus.value) {
      params['filter[status][eq]'] = filterStatus.value;
    }
    const res = await getAIAgentListApi(params);
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
  filterScope.value = undefined;
  filterStatus.value = undefined;
  page.value = 1;
  fetchAgents();
}

const hasActiveFilters = computed(
  () => !!searchKeyword.value || !!filterScope.value || !!filterStatus.value,
);

// ============================================================
// Status toggle
// ============================================================

async function onToggleStatus(agent: AIAgentInfo) {
  if (agent.is_system) return;
  const nextStatus = agent.status === 'disabled' ? 'published' : 'disabled';
  try {
    await updateAIAgentStatusApi(agent.id, nextStatus);
    message.success($t('admin.ai.agent.messages.toggleSuccess'));
    await fetchAgents();
  } catch {
    // handled by interceptor
  }
}

// ============================================================
// Delete
// ============================================================

function onDelete(agent: AIAgentInfo) {
  Modal.confirm({
    title: $t('ui.actionMessage.deleteConfirm', { name: agent.name }),
    content: $t('ui.actionMessage.deleteConfirmContent'),
    okType: 'danger',
    async onOk() {
      try {
        await deleteAIAgentApi(agent.id);
        message.success($t('ui.actionMessage.deleteSuccess'));
        await fetchAgents();
      } catch {
        // handled by interceptor
      }
    },
  });
}

// ============================================================
// Helpers
// ============================================================

function getScopeText(scope: string) {
  const opt = getScopeOptions().find((o) => o.value === scope);
  return opt ? opt.label : scope;
}

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

function getScopeIcon(scope: string): string {
  switch (scope) {
    case 'global': return 'lucide:globe';
    case 'admin': return 'lucide:shield';
    case 'tenant': return 'lucide:building-2';
    default: return 'lucide:circle';
  }
}

// ============================================================
// Stats
// ============================================================

const stats = computed(() => {
  const all = agents.value;
  return {
    total: total.value,
    published: all.filter((a) => a.status === 'published').length,
    system: all.filter((a) => a.is_system).length,
  };
});
</script>

<template>
  <Page
    auto-content-height
    content-class="flex flex-col gap-4"
  >
    <!-- Form Drawer -->
    <AgentForm ref="agentFormRef" @success="fetchAgents" />

    <!-- ==================== Top Bar ==================== -->
    <div class="flex flex-wrap items-center gap-3">
      <!-- Search -->
      <Input
        :value="searchKeyword"
        :placeholder="$t('admin.ai.agent.placeholder.searchName')"
        allow-clear
        class="!w-64"
        @update:value="onSearchInput"
      >
        <template #prefix>
          <IconifyIcon icon="lucide:search" class="size-4 text-muted-foreground" />
        </template>
      </Input>

      <!-- Scope filter -->
      <Select
        v-model:value="filterScope"
        :placeholder="$t('admin.ai.agent.scopeLabel')"
        allow-clear
        class="!w-32"
        @change="onFilterChange"
      >
        <SelectOption
          v-for="opt in getScopeOptions()"
          :key="opt.value"
          :value="opt.value"
        >
          {{ opt.label }}
        </SelectOption>
      </Select>

      <!-- Status filter -->
      <Select
        v-model:value="filterStatus"
        :placeholder="$t('admin.ai.agent.status')"
        allow-clear
        class="!w-32"
        @change="onFilterChange"
      >
        <SelectOption value="published">
          {{ $t('admin.ai.agent.status_options.published') }}
        </SelectOption>
        <SelectOption value="disabled">
          {{ $t('admin.ai.agent.status_options.disabled') }}
        </SelectOption>
        <SelectOption value="draft">
          {{ $t('admin.ai.agent.status_options.draft') }}
        </SelectOption>
      </Select>

      <!-- Clear filters -->
      <Button
        v-if="hasActiveFilters"
        type="link"
        size="small"
        @click="onClearFilters"
      >
        {{ $t('admin.common.reset') }}
      </Button>

      <div class="flex-1" />

      <!-- Stats -->
      <div class="hidden items-center gap-4 text-xs text-muted-foreground md:flex">
        <span>{{ $t('admin.common.total') }} {{ stats.total }}</span>
        <span class="flex items-center gap-1">
          <span class="inline-block size-2 rounded-full bg-green-500" />
          {{ stats.published }}
        </span>
        <span class="flex items-center gap-1">
          <IconifyIcon icon="lucide:shield-check" class="size-3" />
          {{ stats.system }}
        </span>
      </div>

      <!-- Create button -->
      <Button
        v-access:code="['ai_agent:create']"
        type="primary"
        @click="agentFormRef?.openNew()"
      >
        <template #icon>
          <IconifyIcon icon="lucide:plus" class="size-4" />
        </template>
        {{ $t('admin.ai.agent.create') }}
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
          <!-- Header: Avatar + Name + Status -->
          <div class="flex items-start gap-3.5">
            <!-- Avatar -->
            <div
              class="flex size-11 shrink-0 items-center justify-center rounded-xl text-base font-semibold"
              :class="
                agent.is_system
                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                  : 'bg-primary/10 text-primary'
              "
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

            <!-- Name + badges -->
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
                  {{ $t('admin.ai.agent.system') }}
                </Tag>
              </div>
              <!-- Status indicator -->
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

            <!-- Actions dropdown -->
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
                  <MenuItem
                    key="edit"
                    @click="agentFormRef?.openEdit(agent)"
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:pencil" class="size-4" />
                      <span>{{ $t('admin.common.edit') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem
                    v-if="!agent.is_system && agent.status !== 'draft'"
                    key="toggle"
                    @click="onToggleStatus(agent)"
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon
                        :icon="agent.status === 'published' ? 'lucide:pause-circle' : 'lucide:play-circle'"
                        class="size-4"
                      />
                      <span>
                        {{
                          agent.status === 'published'
                            ? $t('admin.ai.agent.status_options.disabled')
                            : $t('admin.ai.agent.status_options.published')
                        }}
                      </span>
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
                      <span>{{ $t('admin.common.delete') }}</span>
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
            {{ $t('admin.ai.agent.noDescription') }}
          </p>

          <!-- Metadata chips -->
          <div class="mt-4 flex flex-wrap items-center gap-2">
            <!-- Model -->
            <Tooltip v-if="agent.model_name" :title="$t('admin.ai.agent.modelName')">
              <div
                class="flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
              >
                <IconifyIcon icon="lucide:brain" class="size-3" />
                <span>{{ agent.model_name }}</span>
              </div>
            </Tooltip>

            <!-- Execution mode -->
            <Tooltip :title="$t('admin.ai.agent.executionMode')">
              <div
                class="flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
              >
                <IconifyIcon :icon="getExecutionModeIcon(agent.execution_mode)" class="size-3" />
                <span>{{ getExecutionModeText(agent.execution_mode) }}</span>
              </div>
            </Tooltip>

            <!-- Scope -->
            <Tag
              :color="getScopeColor(agent.scope)"
              class="!mr-0 !text-[11px]"
              style="padding: 0 6px; line-height: 20px"
            >
              <div class="flex items-center gap-1">
                <IconifyIcon :icon="getScopeIcon(agent.scope)" class="size-3" />
                <span>{{ getScopeText(agent.scope) }}</span>
              </div>
            </Tag>

            <!-- Version -->
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

            <!-- Quick edit button (always visible on mobile) -->
            <button
              class="flex items-center gap-1 rounded-md px-2 py-1 text-primary transition-colors hover:bg-primary/10 md:opacity-0 md:group-hover:opacity-100"
              @click="agentFormRef?.openEdit(agent)"
            >
              <IconifyIcon icon="lucide:pencil" class="size-3" />
              <span>{{ $t('admin.common.edit') }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-else-if="!loading"
        class="flex min-h-[300px] items-center justify-center"
      >
        <Empty :description="$t('admin.common.noData')">
          <Button
            v-access:code="['ai_agent:create']"
            type="primary"
            @click="agentFormRef?.openNew()"
          >
            <template #icon>
              <IconifyIcon icon="lucide:plus" class="size-4" />
            </template>
            {{ $t('admin.ai.agent.create') }}
          </Button>
        </Empty>
      </div>
    </Spin>

    <!-- ==================== Pagination ==================== -->
    <div
      v-if="total > pageSize"
      class="flex justify-end"
    >
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
  </Page>
</template>
