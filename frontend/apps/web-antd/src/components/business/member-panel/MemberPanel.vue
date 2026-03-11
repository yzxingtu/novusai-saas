<script setup lang="ts">
import type { RoleTreeApi } from './data';

import type { OrgMember } from '#/api/admin/organization';

import { computed, onMounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { useDebounceFn } from '@vueuse/core';
import {
  Alert,
  Button,
  Empty,
  Input,
  Pagination,
  Spin,
  Switch,
  Tooltip,
} from 'ant-design-vue';

import { usePresenceStore } from '#/store';

import AdminFormDrawer from './modules/AdminFormDrawer.vue';
import MemberItem from './modules/MemberItem.vue';
import ResetPasswordModal from './modules/ResetPasswordModal.vue';
import { toResetPasswordInfo } from './types';
import { useMemberPanel } from './use-member-panel';

const props = withDefaults(
  defineProps<{
    /** Whether to allow adding members / 是否允许添加成员 */
    allowMembers?: boolean;
    /** API prefix (admin or tenant) / API 前缀 */
    apiPrefix?: 'admin' | 'tenant';
    /** Leader ID / 负责人 ID */
    leaderId?: null | number;
    /** Currently selected node ID / 当前选中的节点 ID */
    nodeId?: null | number;
    /** Node name (for display title) / 节点名称（用于显示标题） */
    nodeName?: string;
    /** Role tree API (select roles in edit mode) / 角色树 API（编辑模式下可选择角色） */
    roleTreeApi?: RoleTreeApi;
    /** Whether to show online status / 是否显示在线状态 */
    showOnlineStatus?: boolean;
  }>(),
  {
    nodeId: null,
    nodeName: '',
    allowMembers: true,
    leaderId: null,
    apiPrefix: 'admin',
    roleTreeApi: undefined,
    showOnlineStatus: false,
  },
);

const emit = defineEmits<{
  (e: 'leaderChanged', leaderId: null | number): void;
  (e: 'memberAdded', member: OrgMember): void;
  (e: 'memberRemoved', memberId: number): void;
  (e: 'refresh'): void;
}>();

const presenceStore = usePresenceStore();

/** Check if member is online / 判断成员是否在线 */
function isMemberOnline(memberId: number): boolean {
  const userType = props.apiPrefix === 'admin' ? 'admin' : 'tenant_admin';
  return presenceStore.isOnline(userType, memberId);
}

// Search keyword (local input, for two-way binding) / 搜索关键词（本地输入，用于双向绑定）
const searchText = ref('');

// Component refs / 组件引用
const adminFormDrawerRef = ref<InstanceType<typeof AdminFormDrawer>>();
const resetPasswordModalRef = ref<InstanceType<typeof ResetPasswordModal>>();

// Use composable / 使用 composable
const {
  members,
  loading,
  operating,
  pagination,
  includeDescendants,
  removeMember,
  setLeader,
  refresh,
  changePage,
  changePageSize,
  search,
  toggleIncludeDescendants,
} = useMemberPanel({
  nodeId: () => props.nodeId,
  apiPrefix: props.apiPrefix,
});

// Debounced search / 防抖搜索
const debouncedSearch = useDebounceFn((keyword: string) => {
  search(keyword);
}, 300);

// Watch input changes, trigger debounced search / 监听输入框变化，触发防抖搜索
watch(searchText, (newValue) => {
  debouncedSearch(newValue);
});

// Watch node changes, reset search box / 监听节点变化，重置搜索框
watch(
  () => props.nodeId,
  () => {
    searchText.value = '';
  },
);

/** Pagination display info / 分页显示信息 */
const paginationInfo = computed(() => {
  const { page, pageSize, total } = pagination.value;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return { start, end, total };
});

/** Handle pagination change / 处理分页变化 */
function handlePaginationChange(page: number, pageSize: number) {
  if (pageSize === pagination.value.pageSize) {
    changePage(page);
  } else {
    changePageSize(pageSize);
  }
}

/** Leader info (leader of current selected node, pinned to top) / 负责人信息（当前选中节点的负责人，用于置顶显示） */
const leaderInfo = computed(() => {
  // When including children, there may be multiple leaders, don't pin in this case / 当包含子节点时，可能有多个负责人，此时不置顶显示
  if (includeDescendants.value) return null;
  // When not including children, find leader of current node / 不包含子节点时，找当前节点的负责人
  return members.value.find((m) => m.isLeader);
});

/** Open create member drawer / 打开创建成员抽屉 */
function handleOpenCreateDrawer() {
  adminFormDrawerRef.value?.openCreate();
}

/** Handle edit member / 处理编辑成员 */
function handleEditMember(member: OrgMember) {
  adminFormDrawerRef.value?.openEdit(member);
}

/** Handle reset password / 处理重置密码 */
function handleResetPassword(member: OrgMember) {
  resetPasswordModalRef.value?.open(toResetPasswordInfo(member));
}

/** Handle member operation success / 处理成员操作成功 */
async function handleMemberSuccess() {
  await refresh();
  emit('refresh');
}

/** Handle remove member / 处理移除成员 */
async function handleRemoveMember(member: OrgMember) {
  // Use member's roleId, supports removing child node members in recursive mode / 使用成员所属 roleId，支持递归模式下移除子节点成员
  const success = await removeMember(member.id, member.roleId);
  if (success) {
    emit('memberRemoved', member.id);
    emit('refresh');
  }
}

/** Handle set leader / 处理设置负责人 */
async function handleSetLeader(member: OrgMember) {
  // Use member's roleId as target node, supports setting leader when including children / 使用成员所属的 roleId 作为目标节点，支持包含子节点时设置负责人
  const success = await setLeader(member.id, member.roleId);
  if (success) {
    emit('leaderChanged', member.id);
    emit('refresh');
  }
}

/** Handle cancel leader / 处理取消负责人 */
async function handleCancelLeader(member: OrgMember) {
  // Use member's roleId as target node / 使用成员所属的 roleId 作为目标节点
  const success = await setLeader(null, member.roleId);
  if (success) {
    emit('leaderChanged', null);
    emit('refresh');
  }
}

/** Refresh member list / 刷新成员列表 */
async function handleRefresh() {
  await refresh();
}

/** Load online status / 加载在线状态 */
onMounted(() => {
  if (props.showOnlineStatus) {
    if (props.apiPrefix === 'admin') {
      presenceStore.loadAdminPresence();
    } else {
      presenceStore.loadCurrentTenantPresence();
    }
    presenceStore.initSocketHandlers();
  }
});
</script>

<template>
  <div class="member-panel flex h-full flex-col">
    <!-- Header: title and actions / 头部：标题和操作 -->
    <div
      class="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700"
    >
      <div class="flex items-center gap-2">
        <IconifyIcon icon="lucide:users" class="h-5 w-5 text-primary" />
        <span class="font-medium text-gray-900 dark:text-gray-100">
          {{ $t('shared.memberPanel.title') }}
        </span>
        <span class="text-sm text-gray-500"> ({{ pagination.total }}) </span>
      </div>
      <div class="flex items-center gap-2">
        <Tooltip :title="$t('shared.memberPanel.refresh')">
          <Button
            type="text"
            size="small"
            :loading="loading"
            @click="handleRefresh"
          >
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" />
            </template>
          </Button>
        </Tooltip>
        <Tooltip
          v-if="!allowMembers"
          :title="$t('shared.memberPanel.nodeNotAllowMembers')"
        >
          <Button type="primary" size="small" disabled>
            <template #icon>
              <IconifyIcon icon="lucide:user-plus" />
            </template>
            {{ $t('shared.memberPanel.addMember') }}
          </Button>
        </Tooltip>
        <Button
          v-else
          type="primary"
          size="small"
          :disabled="!nodeId"
          @click="handleOpenCreateDrawer"
        >
          <template #icon>
            <IconifyIcon icon="lucide:user-plus" />
          </template>
          {{ $t('shared.memberPanel.addMember') }}
        </Button>
      </div>
    </div>

    <!-- Members not allowed hint / 不允许成员提示 -->
    <Alert
      v-if="!allowMembers && nodeId"
      :message="$t('shared.memberPanel.nodeTypeNotAllowMembers')"
      type="warning"
      show-icon
      class="mx-4 mt-3"
    />

    <!-- No node selected hint / 未选择节点提示 -->
    <div
      v-if="!nodeId"
      class="flex flex-1 items-center justify-center text-gray-500"
    >
      <div class="text-center">
        <IconifyIcon
          icon="lucide:mouse-pointer-click"
          class="mx-auto mb-2 h-12 w-12 opacity-50"
        />
        <p>{{ $t('shared.memberPanel.selectNode') }}</p>
      </div>
    </div>

    <template v-else>
      <!-- Search box and recursive query toggle / 搜索框和递归查询开关 -->
      <div class="flex items-center gap-3 px-4 py-3">
        <Input
          v-model:value="searchText"
          :placeholder="$t('shared.memberPanel.searchPlaceholder')"
          allow-clear
          :disabled="loading"
          class="flex-1"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:search" class="text-gray-400" />
          </template>
        </Input>
        <Tooltip :title="$t('shared.memberPanel.includeDescendantsTooltip')">
          <div class="flex flex-shrink-0 items-center gap-1.5">
            <IconifyIcon
              icon="lucide:git-branch"
              class="h-4 w-4 text-gray-400"
            />
            <Switch
              :checked="includeDescendants"
              size="small"
              :disabled="loading"
              @change="(checked) => toggleIncludeDescendants(Boolean(checked))"
            />
            <span class="text-xs text-gray-500">{{
              $t('shared.memberPanel.includeDescendants')
            }}</span>
          </div>
        </Tooltip>
      </div>

      <!-- Member list / 成员列表 -->
      <div class="flex-1 overflow-y-auto px-4">
        <Spin :spinning="loading || operating">
          <template v-if="members.length > 0">
            <!-- Leader pinned to top / 负责人置顶显示 -->
            <template v-if="leaderInfo && !searchText">
              <div class="mb-2 text-xs font-medium uppercase text-gray-500">
                {{ $t('shared.memberPanel.leader') }}
              </div>
              <MemberItem
                :member="leaderInfo"
                :is-leader="true"
                :show-online-status="showOnlineStatus"
                :online="isMemberOnline(leaderInfo.id)"
                @edit="handleEditMember"
                @reset-password="handleResetPassword"
                @remove="handleRemoveMember"
                @set-leader="handleSetLeader"
                @cancel-leader="handleCancelLeader"
              />
              <div
                v-if="members.length > 1"
                class="mb-2 mt-4 text-xs font-medium uppercase text-gray-500"
              >
                {{ $t('shared.memberPanel.members') }}
              </div>
            </template>
            <!-- Other members / 其他成员 -->
            <MemberItem
              v-for="member in members.filter((m) =>
                !searchText && leaderInfo ? m.id !== leaderInfo.id : true,
              )"
              :key="member.id"
              :member="member"
              :is-leader="member.isLeader"
              :show-online-status="showOnlineStatus"
              :online="isMemberOnline(member.id)"
              @edit="handleEditMember"
              @reset-password="handleResetPassword"
              @remove="handleRemoveMember"
              @set-leader="handleSetLeader"
              @cancel-leader="handleCancelLeader"
            />
          </template>
          <Empty
            v-else
            :description="
              searchText
                ? $t('shared.memberPanel.emptySearch')
                : $t('shared.memberPanel.empty')
            "
            class="py-8"
          />
        </Spin>
      </div>

      <!-- Paginator / 分页器 -->
      <div
        v-if="pagination.total > pagination.pageSize"
        class="flex flex-col gap-2 border-t border-gray-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between dark:border-gray-700"
      >
        <div class="text-sm text-gray-500">
          {{
            $t('shared.memberPanel.paginationInfo', {
              start: paginationInfo.start,
              end: paginationInfo.end,
              total: paginationInfo.total,
            })
          }}
        </div>
        <Pagination
          :current="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          :show-size-changer="true"
          :show-quick-jumper="pagination.total > 100"
          :page-size-options="['10', '20', '50', '100']"
          size="small"
          :hide-on-single-page="false"
          @change="handlePaginationChange"
        />
      </div>
    </template>

    <!-- Admin form drawer (create/edit) / 管理员表单抽屉（新建/编辑） -->
    <AdminFormDrawer
      ref="adminFormDrawerRef"
      :node-id="nodeId"
      :node-name="nodeName"
      :api-prefix="apiPrefix"
      :role-tree-api="roleTreeApi"
      @success="handleMemberSuccess"
    />

    <!-- Reset password modal / 重置密码弹窗 -->
    <ResetPasswordModal
      ref="resetPasswordModalRef"
      :api-prefix="apiPrefix"
      :role-id="nodeId || undefined"
      @success="handleMemberSuccess"
    />
  </div>
</template>

<style scoped>
.member-panel {
  background: var(--ant-color-bg-container);
}
</style>
