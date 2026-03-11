<!-- eslint-disable vue/html-closing-bracket-newline -->
<script lang="ts" setup>
import type { TenantRoleType } from '#/api/tenant/role';
/**
 * Tenant organization management page
 * 租户端组织架构管理页面
 * Left org tree + right detail/member panel
 * 左侧组织树 + 右侧详情/成员面板
 */
import type { OrgTreeNodeData } from '#/components/business/org-tree';

import { computed, onMounted, onUnmounted, ref } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Card,
  Empty,
  message,
  Popconfirm,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { deleteTenantRoleApi, getTenantRoleTreeApi } from '#/api/tenant/role';
import { MemberPanel } from '#/components/business/member-panel';
import { OrgNodeDialog } from '#/components/business/org-node-dialog';
import { OrgTreeNode, useOrgTree } from '#/components/business/org-tree';
import { NODE_TYPE_CONFIG } from '#/components/business/org-tree/types';
import { PermissionPreview } from '#/components/business/permission-preview';
import { $t } from '#/locales';

defineOptions({ name: 'TenantOrganization' });

// ============================================================
// Org tree management / 组织树管理
// ============================================================

const {
  treeData,
  loading: treeLoading,
  expandedIds,
  loadRootNodes,
  toggleExpand,
  expandAll,
  collapseAll,
  isExpanded,
  refresh: refreshTree,
  removeNode,
} = useOrgTree({ apiPrefix: 'tenant', immediate: false });

// ============================================================
// Selected node state / 选中节点状态
// ============================================================

const selectedNode = ref<null | OrgTreeNodeData>(null);

/** Left tree panel collapsed state / 左侧树面板折叠状态 */
const treeCollapsed = ref(false);

/** Type config of the selected node / 选中节点的类型配置 */
const selectedNodeTypeConfig = computed(() => {
  if (!selectedNode.value) return null;
  return NODE_TYPE_CONFIG[selectedNode.value.type];
});

/** Handle node selection / 处理节点选中 */
function handleNodeSelect(node: OrgTreeNodeData) {
  selectedNode.value = node;
}

// ============================================================
// Right panel display mode / 右侧面板显示模式
// ============================================================

/** Get translated label for node type / 获取节点类型的翻译标签 */
function getNodeTypeLabel(type: string) {
  return $t(`tenant.system.${type}`);
}

// ============================================================
// Node dialog management / 节点弹窗管理
// ============================================================

const nodeDialogOpen = ref(false);
const nodeDialogMode = ref<'create' | 'edit'>('create');
const nodeDialogParentId = ref<null | number>(null);
const nodeDialogParentType = ref<null | TenantRoleType>(null);
const nodeDialogParentName = ref('');
const nodeDialogNodeId = ref<null | number>(null);

/** Create root node / 创建根节点 */
function handleCreateRoot() {
  nodeDialogMode.value = 'create';
  nodeDialogParentId.value = null;
  nodeDialogParentType.value = null;
  nodeDialogParentName.value = '';
  nodeDialogNodeId.value = null;
  nodeDialogOpen.value = true;
}

/** Create child node under selected node / 在选中节点下创建子节点 */
function handleAddChild(node: OrgTreeNodeData, _type: TenantRoleType) {
  nodeDialogMode.value = 'create';
  nodeDialogParentId.value = node.id;
  nodeDialogParentType.value = node.type;
  nodeDialogParentName.value = node.name;
  nodeDialogNodeId.value = null;
  nodeDialogOpen.value = true;
}

/** Edit node / 编辑节点 */
function handleEditNode(node: OrgTreeNodeData) {
  nodeDialogMode.value = 'edit';
  nodeDialogParentId.value = node.parentId ?? null;
  nodeDialogParentType.value = null;
  nodeDialogParentName.value = '';
  nodeDialogNodeId.value = node.id;
  nodeDialogOpen.value = true;
}

/** Node saved successfully / 节点保存成功 */
function handleNodeSaved() {
  refreshTree();
}

// ============================================================
// Delete node / 删除节点
// ============================================================

const deleting = ref(false);

async function handleDeleteNode(node: OrgTreeNodeData) {
  if (node.hasChildren || node.memberCount > 0) {
    message.warning(
      $t('tenant.system.organization.messages.deleteHasChildren'),
    );
    return;
  }

  deleting.value = true;
  try {
    await deleteTenantRoleApi(node.id);
    message.success($t('tenant.system.organization.messages.deleteSuccess'));
    removeNode(node.id);
    if (selectedNode.value?.id === node.id) {
      selectedNode.value = null;
    }
  } catch {
    message.error($t('shared.common.deleteFailed'));
  } finally {
    deleting.value = false;
  }
}

// ============================================================
// Member panel events / 成员面板事件
// ============================================================

function handleMemberPanelRefresh() {
  // Refresh tree to update member count / 刷新树以更新成员计数
  refreshTree();
}

// ============================================================
// Lifecycle / 生命周期
// ============================================================

onMounted(async () => {
  const firstNode = await loadRootNodes();
  // Auto-select the first root node / 自动选择第一个根节点
  if (firstNode) {
    selectedNode.value = firstNode;
  }
  expandAll();
});

const cleanupPageContext = registerPageContext('tenant/system/organization', () => ({
  page_key: 'tenant.system.organization',
  page_title: $t('tenant.system.organization.name'),
  page_data: {
    resource: '/tenant/organization',
  },
}));

const cleanupPageOps = registerPageOperations('tenant.system.organization', [
  {
    name: 'refresh_tree',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Refresh the organization tree',
    readonly: true,
    handler: async () => {
      await refreshTree();
      return { success: true, message: 'Organization tree refreshed' };
    },
  },
  {
    name: 'create_root_node',
    label: $t('shared.pageOperation.createRecord'),
    description: 'Open dialog to create a root organization node',
    readonly: false,
    handler: async () => {
      handleCreateRoot();
      return { success: true, message: 'Create root node dialog opened' };
    },
  },
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full gap-2 overflow-hidden lg:gap-4">
      <!-- Left: Org tree / 左侧：组织树 -->
      <div
        class="flex flex-shrink-0 flex-col overflow-hidden rounded-xl bg-card shadow-sm transition-all duration-300"
        :class="[
          treeCollapsed ? 'w-12' : 'w-[320px] lg:w-[380px] xl:w-[440px]',
        ]"
      >
        <!-- Toolbar / 工具栏 -->
        <div
          class="flex items-center justify-between border-b border-border/50 px-2 py-2 lg:px-4 lg:py-3"
        >
          <div v-show="!treeCollapsed" class="flex min-w-0 items-center gap-2">
            <IconifyIcon
              icon="lucide:network"
              class="h-4 w-4 flex-shrink-0 text-primary lg:h-5 lg:w-5"
            />
            <span class="truncate text-sm font-medium lg:text-base">{{
              $t('tenant.system.organization.tree')
            }}</span>
          </div>
          <div class="flex items-center gap-0.5 lg:gap-1">
            <template v-if="!treeCollapsed">
              <Tooltip :title="$t('tenant.system.organization.expandAll')">
                <Button type="text" size="small" @click="expandAll">
                  <template #icon>
                    <IconifyIcon
                      icon="lucide:unfold-vertical"
                      class="!text-xs lg:!text-sm"
                    />
                  </template>
                </Button>
              </Tooltip>
              <Tooltip :title="$t('tenant.system.organization.collapseAll')">
                <Button type="text" size="small" @click="collapseAll">
                  <template #icon>
                    <IconifyIcon
                      icon="lucide:fold-vertical"
                      class="!text-xs lg:!text-sm"
                    />
                  </template>
                </Button>
              </Tooltip>
              <Tooltip :title="$t('tenant.system.organization.refresh')">
                <Button
                  type="text"
                  size="small"
                  :loading="treeLoading"
                  @click="refreshTree"
                >
                  <template #icon>
                    <IconifyIcon
                      icon="lucide:refresh-cw"
                      class="!text-xs lg:!text-sm"
                    />
                  </template>
                </Button>
              </Tooltip>
              <Button
                type="primary"
                size="small"
                class="!px-2 lg:!px-3"
                @click="handleCreateRoot"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:plus" />
                </template>
                <span class="hidden sm:inline">{{
                  $t('tenant.system.organization.create')
                }}</span>
              </Button>
            </template>
            <!-- 折叠/展开按钮 -->
            <Tooltip
              :title="
                treeCollapsed
                  ? $t('tenant.system.organization.expandTree')
                  : $t('tenant.system.organization.collapseTree')
              "
            >
              <Button
                type="text"
                size="small"
                @click="treeCollapsed = !treeCollapsed"
              >
                <template #icon>
                  <IconifyIcon
                    :icon="
                      treeCollapsed
                        ? 'lucide:panel-left-open'
                        : 'lucide:panel-left-close'
                    "
                  />
                </template>
              </Button>
            </Tooltip>
          </div>
        </div>

        <!-- 树形列表 -->
        <div v-show="!treeCollapsed" class="flex-1 overflow-y-auto p-2 lg:p-3">
          <Spin :spinning="treeLoading">
            <div v-if="treeData.length > 0" class="space-y-0.5">
              <OrgTreeNode
                v-for="node in treeData"
                :key="node.id"
                :node="node"
                :level="0"
                :expanded-ids="expandedIds"
                :selected-id="selectedNode?.id"
                :is-expanded="isExpanded"
                i18n-prefix="tenant"
                @toggle="toggleExpand"
                @select="handleNodeSelect"
                @edit="handleEditNode"
                @add-child="handleAddChild"
                @delete="handleDeleteNode"
              />
            </div>
            <Empty
              v-else
              :description="$t('tenant.system.organization.empty')"
              class="py-8"
            />
          </Spin>
        </div>
        <!-- 折叠时显示图标 -->
        <div
          v-show="treeCollapsed"
          class="flex flex-1 flex-col items-center gap-2 py-4"
        >
          <Tooltip
            :title="$t('tenant.system.organization.tree')"
            placement="right"
          >
            <IconifyIcon icon="lucide:network" class="h-5 w-5 text-primary" />
          </Tooltip>
        </div>
      </div>

      <!-- Right: Detail/member panel / 右侧：详情/成员面板 -->
      <div
        class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl bg-card shadow-sm"
      >
        <!-- Hint when no node selected / 未选中节点时的提示 -->
        <div
          v-if="!selectedNode"
          class="flex flex-1 items-center justify-center text-muted-foreground"
        >
          <div class="px-4 text-center">
            <IconifyIcon
              icon="lucide:mouse-pointer-click"
              class="mx-auto mb-3 h-12 w-12 opacity-30 lg:h-16 lg:w-16"
            />
            <p class="text-base lg:text-lg">
              {{ $t('tenant.system.organization.selectNodeHint') }}
            </p>
            <p class="mt-1 text-xs lg:text-sm">
              {{ $t('tenant.system.organization.selectNodeSubHint') }}
            </p>
          </div>
        </div>

        <!-- Show details when node selected / 选中节点时显示详情 -->
        <template v-else>
          <!-- Node header + basic info / 节点头部信息 + 基本信息 -->
          <div class="border-b border-border/50 px-3 py-3 lg:px-6 lg:py-4">
            <!-- Row 1: Title and action buttons / 第一行：标题和操作按钮 -->
            <div class="flex items-start justify-between gap-3">
              <div class="flex min-w-0 items-center gap-2 lg:gap-3">
                <div
                  class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10 lg:h-12 lg:w-12"
                >
                  <IconifyIcon
                    :icon="selectedNodeTypeConfig?.icon || 'lucide:folder'"
                    class="h-5 w-5 text-primary lg:h-6 lg:w-6"
                  />
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <h2 class="truncate text-base font-semibold lg:text-xl">
                      {{ selectedNode.name }}
                    </h2>
                    <Tag
                      :class="
                        selectedNode.isActive
                          ? 'border-success/30 bg-success/10 text-success'
                          : ''
                      "
                      class="flex-shrink-0"
                    >
                      {{
                        selectedNode.isActive
                          ? $t('tenant.system.organization.enabled')
                          : $t('tenant.system.organization.disabled')
                      }}
                    </Tag>
                  </div>
                  <div
                    class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground lg:mt-1 lg:gap-x-3 lg:text-sm"
                  >
                    <span>{{
                      getNodeTypeLabel(selectedNodeTypeConfig?.label || '')
                    }}</span>
                    <span>·</span>
                    <span
                      >{{ selectedNode.memberCount
                      }}{{ $t('tenant.system.organization.memberUnit') }}</span
                    >
                    <template v-if="selectedNode.leader">
                      <span>·</span>
                      <span class="flex items-center gap-1">
                        <IconifyIcon
                          icon="lucide:crown"
                          class="h-3 w-3 text-warning"
                        />
                        {{
                          selectedNode.leader.nickname ||
                          selectedNode.leader.username
                        }}
                      </span>
                    </template>
                  </div>
                </div>
              </div>
              <div class="flex flex-shrink-0 gap-2">
                <Button size="small" @click="handleEditNode(selectedNode)">
                  <template #icon>
                    <IconifyIcon icon="lucide:pencil" />
                  </template>
                  <span class="hidden sm:inline">{{
                    $t('shared.common.edit')
                  }}</span>
                </Button>
                <Popconfirm
                  :title="
                    $t('tenant.system.organization.messages.deleteConfirm')
                  "
                  :ok-text="$t('shared.common.confirm')"
                  :cancel-text="$t('shared.common.cancel')"
                  :ok-button-props="{ danger: true }"
                  @confirm="handleDeleteNode(selectedNode)"
                >
                  <Button danger size="small" :loading="deleting">
                    <template #icon>
                      <IconifyIcon icon="lucide:trash-2" />
                    </template>
                    <span class="hidden sm:inline">{{
                      $t('shared.common.delete')
                    }}</span>
                  </Button>
                </Popconfirm>
              </div>
            </div>

            <!-- Row 2: Basic info details / 第二行：基本信息详情 -->
            <div
              class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground lg:text-sm"
            >
              <!-- Code / 编码 -->
              <code class="rounded bg-muted px-1.5 py-0.5 text-xs">{{
                selectedNode.code
              }}</code>
              <!-- Allow members / 允许成员 -->
              <span class="flex items-center gap-1">
                {{ $t('tenant.system.organization.node.allowMembers') }}:
                <Badge
                  :status="selectedNode.allowMembers ? 'success' : 'default'"
                  :text="
                    selectedNode.allowMembers
                      ? $t('tenant.system.organization.yes')
                      : $t('tenant.system.organization.no')
                  "
                />
              </span>
              <!-- Sort order / 排序号 -->
              <span
                >{{ $t('tenant.system.organization.node.sortOrder') }}:
                {{ selectedNode.sortOrder }}</span
              >
              <!-- Permission count / 权限数 -->
              <PermissionPreview
                :node-id="selectedNode.id"
                :permissions-count="selectedNode.permissionsCount ?? 0"
                api-prefix="tenant"
              />
              <!-- Created at / 创建时间 -->
              <span
                >{{ $t('shared.common.createdAt') }}:
                {{ selectedNode.createdAt }}</span
              >
            </div>

            <!-- Row 3: Description (if any) / 第三行：描述（如果有） -->
            <div
              v-if="selectedNode.description"
              class="mt-2 rounded bg-muted/50 px-2 py-1.5 text-xs text-muted-foreground"
            >
              {{ selectedNode.description }}
            </div>
          </div>

          <!-- Member management panel / 成员管理面板 -->
          <div class="flex-1 overflow-hidden p-2 lg:p-4">
            <Card class="h-full overflow-hidden" size="small">
              <template #title>
                <span class="text-sm lg:text-base">{{
                  $t('tenant.system.organization.member.title')
                }}</span>
              </template>
              <MemberPanel
                :node-id="selectedNode.id"
                :node-name="selectedNode.name"
                :allow-members="selectedNode.allowMembers"
                :leader-id="selectedNode.leaderId"
                :role-tree-api="getTenantRoleTreeApi"
                api-prefix="tenant"
                :show-online-status="true"
                @refresh="handleMemberPanelRefresh"
              />
            </Card>
          </div>
        </template>
      </div>
    </div>

    <!-- Node edit dialog / 节点编辑弹窗 -->
    <OrgNodeDialog
      v-model:open="nodeDialogOpen"
      :mode="nodeDialogMode"
      :parent-id="nodeDialogParentId"
      :parent-type="nodeDialogParentType"
      :parent-name="nodeDialogParentName"
      :node-id="nodeDialogNodeId"
      api-prefix="tenant"
      @success="handleNodeSaved"
    />
  </Page>
</template>
