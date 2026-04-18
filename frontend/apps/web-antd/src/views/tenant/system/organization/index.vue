<!-- eslint-disable vue/html-closing-bracket-newline -->
<script lang="ts" setup>
import type {
  TenantOrgNodeInfo,
  TenantOrgNodeType,
} from '#/api/tenant/organization';
import type { OrgTreeNodeData } from '#/components/business/org-tree';
import type { IdentityDetailMeta } from '#/views/_shared/identity/identity-interactions';

import { computed, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Empty,
  message,
  Popconfirm,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  deleteTenantOrganizationNodeApi,
  getTenantOrganizationNodeDetailApi,
  getTenantOrganizationTreeApi,
} from '#/api/tenant/organization';
import IdentityDisplay from '#/components/business/identity-display/IdentityDisplay.vue';
import { MemberPanel } from '#/components/business/member-panel';
import { OrgNodeDialog } from '#/components/business/org-node-dialog';
import {
  getLeaderScopeDescription,
  getLeaderScopeLabel,
} from '#/components/business/org-node-dialog/types';
import { OrgTreeNode, useOrgTree } from '#/components/business/org-tree';
import { NODE_TYPE_CONFIG } from '#/components/business/org-tree/types';
import { PermissionPreview } from '#/components/business/permission-preview';
import { $t } from '#/locales';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

defineOptions({ name: 'TenantOrganization' });

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
  updateNode,
} = useOrgTree({ apiPrefix: 'tenant', immediate: false });

const selectedNode = ref<null | OrgTreeNodeData>(null);
const selectedNodeDetail = ref<null | TenantOrgNodeInfo>(null);
const treeCollapsed = ref(false);
const deleting = ref(false);
const detailLoading = ref(false);

const nodeDialogOpen = ref(false);
const nodeDialogMode = ref<'create' | 'edit'>('create');
const nodeDialogParentId = ref<null | number>(null);
const nodeDialogParentType = ref<null | TenantOrgNodeType>(null);
const nodeDialogParentName = ref('');
const nodeDialogNodeId = ref<null | number>(null);
const nodeDialogCanAssignPermissions = ref(false);

const activeNode = computed(
  () => selectedNodeDetail.value ?? selectedNode.value,
);
const selectedNodeTypeConfig = computed(() => {
  if (!activeNode.value) return null;
  return NODE_TYPE_CONFIG[activeNode.value.type];
});

const leaderDisplayName = computed(() => {
  const leader = activeNode.value?.leader;
  if (!leader) return '';
  return leader.nickname || leader.real_name || leader.username;
});

const leaderIdentityModel = computed(() => {
  const leader = activeNode.value?.leader;
  if (!leader) {
    return null;
  }

  const primary =
    leader.nickname || leader.real_name || leader.username || `#${leader.id}`;

  return {
    avatar: leader.avatar,
    id: leader.id,
    isLeader: true,
    nickname: primary,
    orgNodeName: activeNode.value?.name ?? '',
    secondaryText:
      primary === leader.username ? leader.real_name : leader.username,
    username: leader.username,
  };
});

const leaderIdentityMeta = computed<IdentityDetailMeta>(() => ({
  orgNodeName: activeNode.value?.name,
  scope: 'tenant',
  subjectType: 'tenant_admin',
  username: activeNode.value?.leader?.username,
}));

const leaderScopeLabel = computed(() =>
  getLeaderScopeLabel(activeNode.value?.dataScope),
);

const leaderScopeDescription = computed(() =>
  getLeaderScopeDescription(activeNode.value?.dataScope),
);
function getNodeTypeLabel(type?: string) {
  return type
    ? $t(`tenant.system.organization.nodeType.${type}`)
    : $t('shared.common.unknown');
}

function handleNodeSelect(node: OrgTreeNodeData) {
  selectedNode.value = node;
}

function handleCreateRoot() {
  nodeDialogMode.value = 'create';
  nodeDialogParentId.value = null;
  nodeDialogParentType.value = null;
  nodeDialogParentName.value = '';
  nodeDialogNodeId.value = null;
  nodeDialogCanAssignPermissions.value = true;
  nodeDialogOpen.value = true;
}

async function resolveNodeAssignPermission(nodeId: number): Promise<boolean> {
  if (selectedNodeDetail.value?.id === nodeId) {
    return selectedNodeDetail.value.canAssignPermissions ?? false;
  }

  try {
    const detail = await getTenantOrganizationNodeDetailApi(nodeId);
    if (selectedNode.value?.id === nodeId) {
      selectedNodeDetail.value = detail;
    }
    return detail.canAssignPermissions ?? false;
  } catch {
    return false;
  }
}

async function handleAddChild(node: OrgTreeNodeData, _type: TenantOrgNodeType) {
  nodeDialogMode.value = 'create';
  nodeDialogParentId.value = node.id;
  nodeDialogParentType.value = node.type;
  nodeDialogParentName.value = node.name;
  nodeDialogNodeId.value = null;
  nodeDialogCanAssignPermissions.value = await resolveNodeAssignPermission(
    node.id,
  );
  nodeDialogOpen.value = true;
}

async function handleEditNode(node: OrgTreeNodeData | TenantOrgNodeInfo) {
  nodeDialogMode.value = 'edit';
  nodeDialogParentId.value = node.parentId ?? null;
  nodeDialogParentType.value = null;
  nodeDialogParentName.value = '';
  nodeDialogNodeId.value = node.id;
  nodeDialogCanAssignPermissions.value = await resolveNodeAssignPermission(
    node.id,
  );
  nodeDialogOpen.value = true;
}

async function loadSelectedNodeDetail(nodeId: number) {
  detailLoading.value = true;
  try {
    const detail = await getTenantOrganizationNodeDetailApi(nodeId);
    selectedNodeDetail.value = detail;
    updateNode(nodeId, {
      allowMembers: detail.allowMembers,
      code: detail.code,
      dataScope: detail.dataScope,
      description: detail.description,
      isActive: detail.isActive,
      leader: detail.leader,
      leaderId: detail.leaderId,
      memberCount: detail.memberCount,
      permissionsCount: detail.permissionsCount,
      sortOrder: detail.sortOrder,
      type: detail.type,
    });
  } catch {
    selectedNodeDetail.value = null;
  } finally {
    detailLoading.value = false;
  }
}

async function handleNodeSaved() {
  await refreshTree();
  if (selectedNode.value?.id) {
    await loadSelectedNodeDetail(selectedNode.value.id);
  }
}

async function handleDeleteNode(node: OrgTreeNodeData | TenantOrgNodeInfo) {
  if (node.hasChildren || node.memberCount > 0) {
    message.warning(
      $t('tenant.system.organization.messages.deleteHasChildren'),
    );
    return;
  }

  deleting.value = true;
  try {
    await deleteTenantOrganizationNodeApi(node.id);
    message.success($t('tenant.system.organization.messages.deleteSuccess'));
    removeNode(node.id);
    if (selectedNode.value?.id === node.id) {
      selectedNode.value = null;
      selectedNodeDetail.value = null;
    }
  } catch {
    message.error($t('shared.common.deleteFailed'));
  } finally {
    deleting.value = false;
  }
}

async function handleMemberPanelRefresh() {
  await refreshTree();
  if (selectedNode.value?.id) {
    await loadSelectedNodeDetail(selectedNode.value.id);
  }
}

watch(
  () => selectedNode.value?.id,
  async (nodeId) => {
    if (!nodeId) {
      selectedNodeDetail.value = null;
      return;
    }
    await loadSelectedNodeDetail(nodeId);
  },
);

onMounted(async () => {
  const firstNode = await loadRootNodes();
  if (firstNode) {
    selectedNode.value = firstNode;
  }
});
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full gap-2 overflow-hidden lg:gap-4">
      <div
        class="flex flex-shrink-0 flex-col overflow-hidden rounded-xl bg-card shadow-sm transition-all duration-300"
        :class="[
          treeCollapsed ? 'w-12' : 'w-[320px] lg:w-[380px] xl:w-[440px]',
        ]"
      >
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
                :show-permission-count="false"
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

      <div
        class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl bg-card shadow-sm"
      >
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

        <template v-else>
          <div class="border-b border-border/50 px-3 py-3 lg:px-6 lg:py-4">
            <div class="flex items-start justify-between gap-3">
              <div class="flex min-w-0 items-center gap-2 lg:gap-3">
                <div
                  class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10 lg:h-12 lg:w-12"
                >
                  <IconifyIcon
                    :icon="selectedNodeTypeConfig?.icon || 'lucide:folder-tree'"
                    class="h-5 w-5 text-primary lg:h-6 lg:w-6"
                  />
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <h2 class="truncate text-base font-semibold lg:text-xl">
                      {{ activeNode?.name }}
                    </h2>
                    <Tag
                      :class="
                        activeNode?.isActive
                          ? 'border-success/30 bg-success/10 text-success'
                          : ''
                      "
                      class="flex-shrink-0"
                    >
                      {{
                        activeNode?.isActive
                          ? $t('tenant.system.organization.enabled')
                          : $t('tenant.system.organization.disabled')
                      }}
                    </Tag>
                    <Tag color="blue">
                      {{ getNodeTypeLabel(activeNode?.type) }}
                    </Tag>
                  </div>
                  <div
                    class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground lg:text-sm"
                  >
                    <code class="rounded bg-muted px-1.5 py-0.5 text-xs">{{
                      activeNode?.code
                    }}</code>
                    <span>
                      {{ activeNode?.memberCount
                      }}{{ $t('tenant.system.organization.memberUnit') }}
                    </span>
                    <span
                      v-if="leaderDisplayName"
                      class="flex items-center gap-1"
                    >
                      <IconifyIcon
                        icon="lucide:crown"
                        class="h-3.5 w-3.5 text-warning"
                      />
                      {{ leaderDisplayName }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="flex flex-shrink-0 gap-2">
                <Button size="small" @click="handleEditNode(activeNode!)">
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
                  @confirm="handleDeleteNode(activeNode!)"
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
            <div
              v-if="activeNode?.description"
              class="mt-3 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground"
            >
              {{ activeNode.description }}
            </div>
          </div>

          <div class="flex-1 overflow-y-auto p-2 lg:p-4">
            <Spin :spinning="detailLoading">
              <div class="grid gap-4 xl:grid-cols-3">
                <Card
                  :title="$t('tenant.system.organization.basicInfo')"
                  size="small"
                >
                  <div class="space-y-3 text-sm">
                    <div class="flex items-center justify-between gap-4">
                      <span class="text-muted-foreground">{{
                        $t('tenant.system.organization.node.code')
                      }}</span>
                      <code class="rounded bg-muted px-1.5 py-0.5 text-xs">{{
                        activeNode?.code
                      }}</code>
                    </div>
                    <div class="flex items-center justify-between gap-4">
                      <span class="text-muted-foreground">{{
                        $t('tenant.system.organization.node.type')
                      }}</span>
                      <span>{{ getNodeTypeLabel(activeNode?.type) }}</span>
                    </div>
                    <div class="flex items-center justify-between gap-4">
                      <span class="text-muted-foreground">{{
                        $t('tenant.system.organization.node.allowMembers')
                      }}</span>
                      <span>{{
                        activeNode?.allowMembers
                          ? $t('tenant.system.organization.yes')
                          : $t('tenant.system.organization.no')
                      }}</span>
                    </div>
                    <div class="flex items-center justify-between gap-4">
                      <span class="text-muted-foreground">{{
                        $t('tenant.system.organization.node.sortOrder')
                      }}</span>
                      <span>{{ activeNode?.sortOrder }}</span>
                    </div>
                    <div class="flex items-center justify-between gap-4">
                      <span class="text-muted-foreground">{{
                        $t('tenant.system.organization.memberCount')
                      }}</span>
                      <span>{{ activeNode?.memberCount }}</span>
                    </div>
                    <div class="flex items-center justify-between gap-4">
                      <span class="text-muted-foreground">{{
                        $t('shared.orgNode.permissions')
                      }}</span>
                      <PermissionPreview
                        api-prefix="tenant"
                        source="org-node"
                        :node-id="activeNode!.id"
                        :permissions-count="activeNode?.permissionsCount ?? 0"
                      />
                    </div>
                  </div>
                </Card>

                <Card
                  :title="$t('tenant.system.organization.leaderCardTitle')"
                  size="small"
                >
                  <div class="flex h-full flex-col justify-between gap-3">
                    <div
                      v-if="leaderIdentityModel"
                      class="rounded-xl border border-border/60 bg-background/80 px-3 py-3"
                    >
                      <IdentityTrigger
                        :model="leaderIdentityModel"
                        :meta="leaderIdentityMeta"
                      >
                        <IdentityDisplay
                          :model="leaderIdentityModel"
                          leader-label=""
                        />
                      </IdentityTrigger>
                    </div>
                    <div
                      v-else
                      class="flex items-start gap-3 rounded-xl border border-dashed border-border/60 bg-muted/20 px-3 py-3"
                    >
                      <div
                        class="flex h-10 w-10 items-center justify-center rounded-xl bg-warning/10 text-warning"
                      >
                        <IconifyIcon icon="lucide:crown" class="h-5 w-5" />
                      </div>
                      <div class="min-w-0 flex-1">
                        <div class="text-sm font-medium">
                          {{
                            $t('tenant.system.organization.noLeaderAssigned')
                          }}
                        </div>
                        <div class="mt-1 text-xs text-muted-foreground">
                          {{ $t('tenant.system.organization.noLeaderHint') }}
                        </div>
                      </div>
                    </div>
                    <div
                      class="rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground"
                    >
                      {{
                        $t('tenant.system.organization.leaderCardDescription')
                      }}
                    </div>
                  </div>
                </Card>

                <Card
                  :title="$t('tenant.system.organization.scopeCardTitle')"
                  size="small"
                >
                  <div class="space-y-3 text-sm">
                    <div class="flex items-center justify-between gap-4">
                      <span class="text-muted-foreground">{{
                        $t('tenant.system.organization.scopeMode')
                      }}</span>
                      <Tag color="processing">{{ leaderScopeLabel }}</Tag>
                    </div>
                    <div
                      class="rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground"
                    >
                      {{ leaderScopeDescription }}
                    </div>
                    <div
                      v-if="(activeNode?.customDeptIds?.length || 0) > 0"
                      class="flex items-center justify-between gap-4"
                    >
                      <span class="text-muted-foreground">{{
                        $t('tenant.system.organization.scopeTargetCount')
                      }}</span>
                      <span>{{ activeNode?.customDeptIds?.length }}</span>
                    </div>
                  </div>
                </Card>
              </div>

              <Card class="mt-4 h-[520px] overflow-hidden" size="small">
                <template #title>
                  <span class="text-sm lg:text-base">{{
                    $t('tenant.system.organization.member.title')
                  }}</span>
                </template>
                <template #extra>
                  <span class="text-xs text-muted-foreground">
                    {{ $t('tenant.system.organization.memberCardDescription') }}
                  </span>
                </template>
                <MemberPanel
                  :node-id="selectedNode.id"
                  :node-name="selectedNode.name"
                  :allow-members="activeNode?.allowMembers"
                  :leader-id="activeNode?.leaderId"
                  :org-tree-api="getTenantOrganizationTreeApi"
                  api-prefix="tenant"
                  :show-online-status="true"
                  @refresh="handleMemberPanelRefresh"
                />
              </Card>
            </Spin>
          </div>
        </template>
      </div>
    </div>

    <OrgNodeDialog
      v-model:open="nodeDialogOpen"
      :mode="nodeDialogMode"
      :parent-id="nodeDialogParentId"
      :parent-type="nodeDialogParentType"
      :parent-name="nodeDialogParentName"
      :node-id="nodeDialogNodeId"
      api-prefix="tenant"
      :can-assign-permissions="nodeDialogCanAssignPermissions"
      @success="handleNodeSaved"
    />
  </Page>
</template>
