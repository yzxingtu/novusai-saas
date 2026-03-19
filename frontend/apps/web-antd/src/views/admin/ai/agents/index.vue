<script lang="ts" setup>
/**
 * Agent management list page (platform) — useCrudList + card grid
 * 智能体管理列表页面（平台端）— useCrudList + 卡片网格
 *
 * Uses useCrudList for core CRUD (list/pagination/search/delete/recycle bin),
 * 使用 useCrudList 管理核心 CRUD（列表/分页/搜索/删除/回收站），
 * retains custom logic: publish, version history, status toggle, AgentForm ref mode.
 * 保留自定义逻辑：发布、版本历史、状态切换、AgentForm ref 模式。
 */
import type { AIAgentInfo } from '#/api/admin/ai';

import { computed, ref, watchEffect } from 'vue';

import { Page, useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
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

import { RecycleBinDrawer } from '#/adapter/vxe-table/components';
import {
  deleteAIAgentApi,
  getAIAgentListApi,
  publishAIAgentApi,
  updateAIAgentStatusApi,
} from '#/api/admin/ai';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';
import { getScopeIcon, getScopeText } from '#/utils/scope-helpers';

import {
  getAudienceColor,
  getAudienceText,
  getExecutionModeText,
  getFormDefaults,
  getScopeColor,
  getScopeOptions,
  getStatusText,
  useFormSchema,
} from './data';

const AI_PAGE_KEY = 'admin.ai.agents';
import AgentForm from './modules/form.vue';
import VersionHistoryDrawer from './modules/VersionHistory.vue';

defineOptions({ name: 'AIAgentList' });

// ============================================================
// Declarative CRUD (list/pagination/search/delete/recycle bin) / 声明式 CRUD（列表/分页/搜索/删除/回收站）
// ============================================================

const agentSummary = ref({ published: 0, system: 0 });

const {
  list,
  total,
  loading,
  currentPage,
  pageSize,
  searchKeyword,
  loadList,
  onSearch,
  onPageChange,
  handleMenuAction,
} = useCrudList<AIAgentInfo>({
  api: {
    list: getAIAgentListApi,
    delete: deleteAIAgentApi,
    resource: '/admin/ai/agents',
  },
  i18nPrefix: 'admin.ai.agent',
  nameField: 'name',
  defaultSort: '-created_at',
  pageSize: 12,
  recycleBin: true,
  customActions: {
    edit: (row) => agentFormRef.value?.openEdit(row, { _aiPageKey: AI_PAGE_KEY }),
  },
  ai: {
    pageKey: AI_PAGE_KEY,
    formSchema: (isEdit?: boolean) => useFormSchema(isEdit ?? false, false, !(isEdit ?? false)),
    entityName: $t('admin.ai.agent.name'),
    entityDescription: $t('admin.ai.agent.entityDescription'),
    openRecycleBin: () => recycleBinRef.value?.open(),
    contextExtras: () => ({
      published: agentSummary.value.published,
      system: agentSummary.value.system,
    }),
    extra: [
      {
        name: 'create_record',
        label: $t('shared.pageOperation.createRecord'),
        description: 'Open the create agent form and optionally pre-fill fields / 打开新建智能体表单，可选预填字段',
        readonly: false,
        params: {
          name: { type: 'string', description: 'Agent name / 智能体名称' },
          description: { type: 'string', description: 'Agent description / 简介' },
          model_id: { type: 'number', description: 'AI model ID / AI 模型 ID' },
          system_prompt: { type: 'string', description: 'System prompt / 系统提示词' },
          welcome_message: { type: 'string', description: 'Welcome message / 欢迎语' },
        },
        handler: async (params): Promise<{ success: boolean; message: string }> => {
          const overrides: Record<string, unknown> = {};
          if (params?.name) overrides.name = params.name;
          if (params?.description) overrides.description = params.description;
          if (params?.model_id) overrides.model_id = params.model_id;
          if (params?.system_prompt) overrides.system_prompt = params.system_prompt;
          if (params?.welcome_message) overrides.welcome_message = params.welcome_message;

          const extraData: Record<string, unknown> = { _aiPageKey: AI_PAGE_KEY };
          if (Object.keys(overrides).length > 0) {
            extraData._defaults = { ...getFormDefaults(), ...overrides };
          }
          agentFormRef.value?.openNew(extraData);

          const filled = Object.keys(overrides);
          return {
            success: true,
            message: filled.length > 0
              ? `Create agent form opened with pre-filled: ${filled.join(', ')} / 表单已打开，预填: ${filled.join(', ')}`
              : 'Create agent form opened / 新建表单已打开',
          };
        },
      },
      {
        name: 'search',
        label: $t('shared.pageOperation.searchByKeyword'),
        description: 'Search agents by keyword / 按关键词搜索智能体',
        readonly: true,
        params: {
          keyword: { type: 'string', description: 'Search keyword / 搜索关键词' },
        },
        handler: async (params): Promise<{ success: boolean; message: string }> => {
          const keyword = (params?.keyword as string) || '';
          searchKeyword.value = keyword;
          doSearch();
          return { success: true, message: `Searched for: ${keyword} / 已搜索：${keyword}` };
        },
      },
    ],
  },
});

// ========== Recycle bin / 回收站 ==========
const recycleBinRef = ref<null | { deletedCount: number; open: () => void }>(
  null,
);
const recycleBinCount = computed(() => recycleBinRef.value?.deletedCount ?? 0);
function openRecycleBin() {
  recycleBinRef.value?.open();
}

// ============================================================
// AgentForm (ref mode, non-standard FormDrawer) / AgentForm（ref 模式，非标准 FormDrawer）
// ============================================================

const agentFormRef = ref<InstanceType<typeof AgentForm>>();

function onCreateAgent() {
  agentFormRef.value?.openNew({ _aiPageKey: AI_PAGE_KEY });
}

function onEditAgent(agent: AIAgentInfo) {
  agentFormRef.value?.openEdit(agent, { _aiPageKey: AI_PAGE_KEY });
}

// ============================================================
// Version history / 版本历史
// ============================================================

const [VersionDrawer, versionDrawerApi] = useVbenDrawer({
  connectedComponent: VersionHistoryDrawer,
});

function onVersions(agent: AIAgentInfo) {
  versionDrawerApi.setData({
    id: agent.id,
    publishedVersion: agent.published_version ?? null,
  });
  versionDrawerApi.open();
}

// ============================================================
// Publish modal / 发布弹窗
// ============================================================

const publishModalOpen = ref(false);
const publishChangeLog = ref('');
const publishLoading = ref(false);
let publishAgentId = 0;

function onPublish(agent: AIAgentInfo) {
  publishAgentId = agent.id;
  publishChangeLog.value = '';
  publishModalOpen.value = true;
}

async function onPublishConfirm() {
  publishLoading.value = true;
  try {
    await publishAIAgentApi(publishAgentId, {
      change_log: publishChangeLog.value || null,
    });
    message.success($t('admin.ai.agent.messages.publishSuccess'));
    publishModalOpen.value = false;
    await loadList();
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  } finally {
    publishLoading.value = false;
  }
}

// ============================================================
// Status toggle (non-standard toggle, agents have published/disabled/draft) / 状态切换（非标准 toggle，智能体有 published/disabled/draft）
// ============================================================

async function onToggleStatus(agent: AIAgentInfo) {
  if (agent.is_system) return;
  const nextStatus = agent.status === 'disabled' ? 'published' : 'disabled';
  try {
    await updateAIAgentStatusApi(agent.id, nextStatus);
    message.success($t('admin.ai.agent.messages.toggleSuccess'));
    await loadList();
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  }
}

// ============================================================
// Search filters / 搜索过滤
// ============================================================

const filterScope = ref<string>();
const filterStatus = ref<string>();

function doSearch() {
  const params: Record<string, unknown> = {};
  if (searchKeyword.value.trim()) {
    params['filter[name][ilike]'] = searchKeyword.value.trim();
  }
  if (filterScope.value) {
    params['filter[scope][eq]'] = filterScope.value;
  }
  if (filterStatus.value) {
    params['filter[status][eq]'] = filterStatus.value;
  }
  onSearch(params);
}

function onClearFilters() {
  searchKeyword.value = '';
  filterScope.value = undefined;
  filterStatus.value = undefined;
  onSearch({});
}

const hasActiveFilters = computed(
  () => !!searchKeyword.value || !!filterScope.value || !!filterStatus.value,
);

// ============================================================
// Helper functions / 辅助函数
// ============================================================

function getStatusDotClass(status: string): string {
  switch (status) {
    case 'disabled': {
      return 'bg-red-400';
    }
    case 'published': {
      return 'bg-green-500';
    }
    default: {
      return 'bg-gray-400';
    }
  }
}

function getExecutionModeIcon(mode: string): string {
  switch (mode) {
    case 'api': {
      return 'lucide:code';
    }
    case 'batch': {
      return 'lucide:layers';
    }
    case 'conversation': {
      return 'lucide:message-circle';
    }
    case 'task': {
      return 'lucide:list-checks';
    }
    default: {
      return 'lucide:bot';
    }
  }
}

watchEffect(() => {
  const all = list.value;
  agentSummary.value = {
    published: all.filter((a) => a.status === 'published').length,
    system: all.filter((a) => a.is_system).length,
  };
});

const stats = computed(() => {
  const all = list.value;
  return {
    total: total.value,
    published: all.filter((a) => a.status === 'published').length,
    system: all.filter((a) => a.is_system).length,
  };
});

</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- Form Drawer -->
    <AgentForm ref="agentFormRef" @success="loadList" />
    <VersionDrawer @success="loadList" />
    <RecycleBinDrawer
      ref="recycleBinRef"
      resource="/admin/ai/agents"
      @restored="loadList"
    />
    <!-- Publish Modal -->
    <Modal
      v-model:open="publishModalOpen"
      :title="$t('admin.ai.agent.messages.publishTitle')"
      :confirm-loading="publishLoading"
      @ok="onPublishConfirm"
    >
      <p class="mb-2 text-muted-foreground">
        {{ $t('admin.ai.agent.messages.publishDesc') }}
      </p>
      <Input.TextArea
        v-model:value="publishChangeLog"
        :placeholder="$t('admin.ai.agent.messages.changeLogPlaceholder')"
        :rows="3"
        :maxlength="2000"
        show-count
      />
    </Modal>

    <!-- ==================== Top Bar ==================== -->
    <div class="flex flex-wrap items-center gap-3">
      <!-- Search -->
      <Input
        :value="searchKeyword"
        :placeholder="$t('admin.ai.agent.placeholder.searchName')"
        allow-clear
        class="!w-64"
        @update:value="
          (v: string) => {
            searchKeyword = v;
            doSearch();
          }
        "
      >
        <template #prefix>
          <IconifyIcon
            icon="lucide:search"
            class="size-4 text-muted-foreground"
          />
        </template>
      </Input>

      <!-- Scope filter -->
      <Select
        v-model:value="filterScope"
        :placeholder="$t('admin.ai.agent.scopeLabel')"
        allow-clear
        class="!w-32"
        @change="doSearch"
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
        @change="doSearch"
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

      <div class="flex-1"></div>

      <!-- Stats -->
      <div
        class="hidden items-center gap-4 text-xs text-muted-foreground md:flex"
      >
        <span>{{ $t('admin.common.total') }} {{ stats.total }}</span>
        <span class="flex items-center gap-1">
          <span class="inline-block size-2 rounded-full bg-green-500"></span>
          {{ stats.published }}
        </span>
        <span class="flex items-center gap-1">
          <IconifyIcon icon="lucide:shield-check" class="size-3" />
          {{ stats.system }}
        </span>
      </div>

      <!-- Recycle bin / 回收站 -->
      <span v-access:code="['ai_agent:recycle_bin']">
        <Tooltip :title="$t('common.recycleBin.title')">
          <Badge :count="recycleBinCount" :offset="[-2, 2]" size="small">
            <Button @click="openRecycleBin">
              <template #icon>
                <IconifyIcon icon="lucide:trash-2" class="size-4" />
              </template>
            </Button>
          </Badge>
        </Tooltip>
      </span>

      <!-- Create button -->
      <Button
        v-access:code="['ai_agent:create']"
        type="primary"
        @click="onCreateAgent"
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
        v-if="list.length > 0"
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
      >
        <div
          v-for="agent in list"
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
                v-if="agent.avatar && !String(agent.avatar).includes(':')"
                :src="toAvatarDisplayUrl(agent.avatar)"
                :alt="agent.name"
                class="size-full rounded-xl object-cover"
              />
              <IconifyIcon
                v-else-if="agent.avatar && String(agent.avatar).includes(':')"
                :icon="String(agent.avatar)"
                class="size-5"
              />
              <span v-else>{{
                agent.name?.charAt(0)?.toUpperCase() || '?'
              }}</span>
            </div>

            <!-- Name + badges -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <h3
                  class="cursor-pointer truncate text-sm font-semibold text-foreground hover:text-primary"
                  @click="$router.push(`/admin/ai/agents/${agent.id}`)"
                >
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
                ></span>
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
                    key="detail"
                    @click="
                      $router.push(`/admin/ai/agents/${agent.id}`)
                    "
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:settings" class="size-4" />
                      <span>{{ $t('admin.ai.agent.detail.title') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem key="edit" @click="onEditAgent(agent)">
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
                        :icon="
                          agent.status === 'published'
                            ? 'lucide:pause-circle'
                            : 'lucide:play-circle'
                        "
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
                    v-if="!agent.is_system && agent.status === 'draft'"
                    key="publish"
                    @click="onPublish(agent)"
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon
                        icon="lucide:rocket"
                        class="size-4 text-success"
                      />
                      <span>{{ $t('admin.ai.agent.actions.publish') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem
                    key="routing"
                    @click="
                      $router.push(`/admin/ai/agents/${agent.id}?tab=routing`)
                    "
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon
                        icon="lucide:git-branch"
                        :class="
                          (
                            agent.routing_config as Record<
                              string,
                              unknown
                            > | null
                          )?.enable_routing
                            ? 'size-4 text-green-500'
                            : 'size-4'
                        "
                      />
                      <span>{{ $t('admin.ai.agent.detail.routing') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem key="versions" @click="onVersions(agent)">
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:history" class="size-4" />
                      <span>{{ $t('admin.ai.agent.actions.versions') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem
                    v-if="!agent.is_system"
                    key="delete"
                    class="!text-destructive"
                    @click="handleMenuAction('delete', agent)"
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
            <Tooltip
              v-if="agent.model_name"
              :title="$t('admin.ai.agent.modelName')"
            >
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
                <IconifyIcon
                  :icon="getExecutionModeIcon(agent.execution_mode)"
                  class="size-3"
                />
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

            <!-- Target Audience -->
            <Tag
              :color="getAudienceColor(agent.target_audience)"
              class="!mr-0 !text-[11px]"
              style="padding: 0 6px; line-height: 20px"
            >
              <div class="flex items-center gap-1">
                <IconifyIcon icon="lucide:users" class="size-3" />
                <span>{{ getAudienceText(agent.target_audience) }}</span>
              </div>
            </Tag>

            <!-- Smart Routing indicator -->
            <Tooltip
              v-if="
                (agent.routing_config as Record<string, unknown> | null)
                  ?.enable_routing
              "
              :title="$t('admin.ai.agent.routing.statusEnabled')"
            >
              <div
                class="flex items-center gap-1 rounded-md bg-green-500/10 px-2 py-1 text-[11px] font-medium text-green-600 dark:text-green-400"
              >
                <IconifyIcon icon="lucide:git-branch" class="size-3" />
                <span>{{ $t('admin.ai.agent.routing.statusEnabled') }}</span>
              </div>
            </Tooltip>

            <!-- Skill Packages -->
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
              :title="
                agent.skill_packages
                  .slice(3)
                  .map((p: { name: string }) => p.name)
                  .join(', ')
              "
            >
              <Tag
                color="cyan"
                class="!mr-0 !text-[11px]"
                style="padding: 0 6px; line-height: 20px"
              >
                +{{ agent.skill_packages.length - 3 }}
              </Tag>
            </Tooltip>

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

            <div class="flex items-center gap-2">
              <!-- Detail/Configure button -->
              <button
                class="flex items-center gap-1 rounded-md px-2 py-1 text-primary transition-colors hover:bg-primary/10"
                @click="$router.push(`/admin/ai/agents/${agent.id}`)"
              >
                <IconifyIcon icon="lucide:settings" class="size-3" />
                <span>{{ $t('admin.ai.agent.detail.title') }}</span>
              </button>
              <!-- Quick edit button -->
              <button
                class="flex items-center gap-1 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                @click="onEditAgent(agent)"
              >
                <IconifyIcon icon="lucide:pencil" class="size-3" />
                <span>{{ $t('admin.common.edit') }}</span>
              </button>
            </div>
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
            @click="onCreateAgent"
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
    <div v-if="total > pageSize" class="flex justify-end">
      <Pagination
        :current="currentPage"
        :page-size="pageSize"
        :total="total"
        :page-size-options="['12', '24', '48']"
        :show-size-changer="false"
        size="small"
        @change="onPageChange"
      />
    </div>
  </Page>
</template>
