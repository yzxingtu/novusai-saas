<script lang="ts" setup>
/**
 * Tenant agent management list page — useCrudList + card grid
 * 企业端智能体管理列表页面 — useCrudList + 卡片网格
 *
 * useCrudList manages: list/pagination/search/delete/recycle bin
 * useCrudList 管理：列表/分页/搜索/删除/回收站
 * Custom: AgentForm ref mode/publish/version history
 * 自定义：AgentForm ref 模式/发布/版本历史
 */
import type { AgentListItem } from '#/api/tenant/agents';

import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';

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
  deleteAgentApi,
  getAgentListApi,
  publishAgentApi,
} from '#/api/tenant/agents';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatRelativeTime } from '#/utils/common';
import { toAvatarDisplayUrl } from '#/utils/image';

import {
  getAudienceColor,
  getAudienceText,
  getExecutionModeText,
  getStatusText,
  useFormSchema,
} from './data';

const AI_PAGE_KEY = 'tenant.ai.agents';
import AgentForm from './modules/AgentForm.vue';
import VersionHistory from './modules/VersionHistory.vue';

defineOptions({ name: 'TenantAgentList' });

// ============================================================
// Declarative CRUD / 声明式 CRUD
// ============================================================

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
} = useCrudList<AgentListItem>({
  api: {
    list: getAgentListApi,
    delete: deleteAgentApi,
    resource: '/tenant/ai/agents',
  },
  i18nPrefix: 'tenant.ai.agent',
  nameField: 'name',
  defaultSort: '-created_at',
  pageSize: 12,
  recycleBin: true,
  customActions: {
    edit: (row) => agentFormRef.value?.openEdit(row, { _aiPageKey: AI_PAGE_KEY }),
  },
  ai: {
    pageKey: AI_PAGE_KEY,
    formSchema: (isEdit?: boolean) => useFormSchema(!(isEdit ?? false)),
    entityName: $t('tenant.ai.agent.name'),
    entityDescription: $t('tenant.ai.agent.entityDescription'),
    openRecycleBin: () => recycleBinRef.value?.open(),
    contextExtras: () => ({
      published: stats.value.published,
      system: stats.value.system,
    }),
    extra: [
      {
        name: 'create_record',
        label: $t('shared.pageOperation.createRecord'),
        description: 'Open the create agent form / 打开新建智能体表单',
        readonly: false,
        handler: async (): Promise<{ success: boolean; message: string }> => {
          agentFormRef.value?.openNew({ _aiPageKey: AI_PAGE_KEY });
          return { success: true, message: 'Create agent form opened / 新建表单已打开' };
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
          searchKeyword.value = (params?.keyword as string) || '';
          onSearch({ 'filter[name][ilike]': searchKeyword.value || undefined });
          return { success: true, message: `Searched for: ${searchKeyword.value} / 已搜索：${searchKeyword.value}` };
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
// AgentForm (ref mode) / AgentForm（ref 模式）
// ============================================================

const router = useRouter();
const agentFormRef = ref<InstanceType<typeof AgentForm>>();

function onCreateAgent() {
  agentFormRef.value?.openNew({ _aiPageKey: AI_PAGE_KEY });
}

function onEditAgent(agent: AgentListItem) {
  agentFormRef.value?.openEdit(agent, { _aiPageKey: AI_PAGE_KEY });
}

// ============================================================
// Version history / 版本历史
// ============================================================

const [VersionHistoryDrawer, versionHistoryApi] = useVbenDrawer({
  connectedComponent: VersionHistory,
});

function onVersions(agent: AgentListItem) {
  versionHistoryApi.setData({
    id: agent.id,
    publishedVersion: agent.published_version ?? null,
  });
  versionHistoryApi.open();
}

// ============================================================
// Publish / 发布
// ============================================================

const publishModalOpen = ref(false);
const publishChangeLog = ref('');
const publishLoading = ref(false);
let publishAgentId = 0;

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
    await loadList();
  } catch {
    // handled by interceptor / 错误由请求拦截器处理
  } finally {
    publishLoading.value = false;
  }
}

// ============================================================
// Search filters / 搜索过滤
// ============================================================

const filterStatus = ref<string>();

function doSearch() {
  const params: Record<string, unknown> = {};
  if (searchKeyword.value.trim()) {
    params['filter[name][ilike]'] = searchKeyword.value.trim();
  }
  if (filterStatus.value) {
    params['filter[status][eq]'] = filterStatus.value;
  }
  onSearch(params);
}

function onClearFilters() {
  searchKeyword.value = '';
  filterStatus.value = undefined;
  onSearch({});
}

const hasActiveFilters = computed(
  () => !!searchKeyword.value || !!filterStatus.value,
);

// ============================================================
// Helpers / 辅助
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

const stats = computed(() => ({
  total: total.value,
  published: list.value.filter((a) => a.status === 'published').length,
  system: list.value.filter((a) => a.is_system).length,
}));

</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- Drawers -->
    <AgentForm ref="agentFormRef" @success="loadList" />
    <VersionHistoryDrawer @success="loadList" />
    <RecycleBinDrawer
      ref="recycleBinRef"
      resource="/tenant/ai/agents"
      @restored="loadList"
    />

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

      <Select
        v-model:value="filterStatus"
        :placeholder="$t('tenant.ai.agent.status')"
        allow-clear
        class="!w-32"
        @change="doSearch"
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

      <div class="flex-1"></div>

      <div
        class="hidden items-center gap-4 text-xs text-muted-foreground md:flex"
      >
        <span>{{ $t('common.total') }} {{ stats.total }}</span>
        <span class="flex items-center gap-1">
          <span class="inline-block size-2 rounded-full bg-green-500"></span>
          {{ stats.published }}
        </span>
      </div>

      <!-- Recycle bin / 回收站 -->
      <span v-access:code="['agent:recycle_bin']">
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

      <Button
        v-access:code="['agent:create']"
        type="primary"
        @click="onCreateAgent"
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
        v-if="list.length > 0"
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
      >
        <div
          v-for="agent in list"
          :key="agent.id"
          class="group relative rounded-xl border border-border bg-card p-5 transition-all duration-200 hover:border-primary/30 hover:shadow-md"
        >
          <!-- Header -->
          <div class="flex items-start gap-3.5">
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

            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <h3
                  class="cursor-pointer truncate text-sm font-semibold text-foreground hover:text-primary"
                  @click="router.push(`/tenant/ai/agents/${agent.id}`)"
                >
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
                ></span>
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
                  <MenuItem
                    key="detail"
                    @click="router.push(`/tenant/ai/agents/${agent.id}`)"
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon icon="lucide:settings" class="size-4" />
                      <span>{{ $t('tenant.ai.agent.detail.title') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem key="edit" @click="onEditAgent(agent)">
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
                      <IconifyIcon
                        icon="lucide:rocket"
                        class="size-4 text-success"
                      />
                      <span>{{ $t('tenant.ai.agent.actions.publish') }}</span>
                    </div>
                  </MenuItem>
                  <MenuItem
                    key="routing"
                    @click="
                      router.push(
                        `/tenant/ai/agents/${agent.id}?tab=routing`,
                      )
                    "
                  >
                    <div class="flex items-center gap-2">
                      <IconifyIcon
                        icon="lucide:git-branch"
                        class="size-4"
                      />
                      <span>{{
                        $t('tenant.ai.agent.detail.routing')
                      }}</span>
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
                    @click="handleMenuAction('delete', agent)"
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
            <Tooltip
              v-if="agent.model_name"
              :title="$t('tenant.ai.agent.modelName')"
            >
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
                <IconifyIcon
                  :icon="getExecutionModeIcon(agent.execution_mode)"
                  class="size-3"
                />
                <span>{{ getExecutionModeText(agent.execution_mode) }}</span>
              </div>
            </Tooltip>

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
              <button
                class="flex items-center gap-1 rounded-md px-2 py-1 text-primary transition-colors hover:bg-primary/10"
                @click="router.push(`/tenant/ai/agents/${agent.id}`)"
              >
                <IconifyIcon icon="lucide:settings" class="size-3" />
                <span>{{ $t('tenant.ai.agent.detail.title') }}</span>
              </button>
              <button
                class="flex items-center gap-1 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                @click="onEditAgent(agent)"
              >
                <IconifyIcon icon="lucide:pencil" class="size-3" />
                <span>{{ $t('common.edit') }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div
        v-else-if="!loading"
        class="flex min-h-[300px] items-center justify-center"
      >
        <Empty :description="$t('common.noData')">
          <Button
            v-access:code="['agent:create']"
            type="primary"
            @click="onCreateAgent"
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
