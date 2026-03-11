import type { OrgTreeNodeData, UseOrgTreeReturn } from './types';

/**
 * Organization tree management hook
 * Supports both admin and tenant API prefixes
 * 组织树管理 hook
 * 支持 admin 和 tenant 两种 API 前缀
 */
import type { OrgNodeInfo } from '#/api/admin/organization';

import { ref, shallowRef } from 'vue';

import {
  getNodeChildrenApi,
  getOrganizationRootNodesApi,
} from '#/api/admin/organization';
import {
  getTenantNodeChildrenApi,
  getTenantOrganizationRootNodesApi,
} from '#/api/tenant/organization';

/** useOrgTree options / useOrgTree 选项 */
export interface UseOrgTreeOptions {
  /** API prefix: 'admin' or 'tenant' / API 前缀 */
  apiPrefix?: 'admin' | 'tenant';
  /** Whether to load root nodes immediately / 是否立即加载根节点 */
  immediate?: boolean;
}

/**
 * Convert OrgNodeInfo to OrgTreeNodeData
 * 将 OrgNodeInfo 转换为 OrgTreeNodeData
 */
function toTreeNode(node: OrgNodeInfo): OrgTreeNodeData {
  return {
    ...node,
    children: [],
    loading: false,
    loaded: false,
  };
}

/**
 * Recursively find a node by ID
 * 递归查找节点
 */
function findNode(
  nodes: OrgTreeNodeData[],
  id: number,
): null | OrgTreeNodeData {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.children.length > 0) {
      const found = findNode(node.children, id);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Collect all node IDs (for expanding all)
 * 收集所有节点 ID（用于展开全部）
 */
function collectAllIds(nodes: OrgTreeNodeData[]): number[] {
  const ids: number[] = [];
  for (const node of nodes) {
    ids.push(node.id);
    if (node.children.length > 0) {
      ids.push(...collectAllIds(node.children));
    }
  }
  return ids;
}

/**
 * Organization Tree Business Logic Composable
 * 组织树业务逻辑 composable
 */
export function useOrgTree(options: UseOrgTreeOptions = {}): UseOrgTreeReturn {
  const { apiPrefix = 'admin', immediate = true } = options;

  // Admin API / 管理端 API
  const api =
    apiPrefix === 'admin'
      ? {
          getRootNodes: getOrganizationRootNodesApi,
          getChildren: getNodeChildrenApi,
        }
      : {
          getRootNodes: getTenantOrganizationRootNodesApi,
          getChildren: getTenantNodeChildrenApi,
        };

  // State
  const treeData = shallowRef<OrgTreeNodeData[]>([]);
  const loading = ref(false);
  const expandedIds = ref<Set<number>>(new Set());

  /**
   * Load root nodes
   * 加载根节点
   * @returns First root node (for auto-select)
   */
  async function loadRootNodes(): Promise<null | OrgTreeNodeData> {
    loading.value = true;
    try {
      const nodes = await api.getRootNodes();
      treeData.value = nodes.map((node) => toTreeNode(node));
      return treeData.value[0] ?? null;
    } catch {
      treeData.value = [];
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Recursively clone and update nodes
   */
  function cloneAndUpdate(
    nodes: OrgTreeNodeData[],
    targetId: number,
    updater: (node: OrgTreeNodeData) => OrgTreeNodeData,
  ): OrgTreeNodeData[] {
    return nodes.map((node) => {
      if (node.id === targetId) {
        return updater({ ...node });
      }
      if (node.children.length > 0) {
        return {
          ...node,
          children: cloneAndUpdate(node.children, targetId, updater),
        };
      }
      return node;
    });
  }

  /**
   * Load child nodes
   * 加载子节点
   */
  async function loadChildren(nodeId: number): Promise<void> {
    const node = findNode(treeData.value, nodeId);
    if (!node || node.loaded) return;

    // Set loading state
    treeData.value = cloneAndUpdate(treeData.value, nodeId, (n) => ({
      ...n,
      loading: true,
    }));

    try {
      const children = await api.getChildren(nodeId);
      treeData.value = cloneAndUpdate(treeData.value, nodeId, (n) => ({
        ...n,
        children: children.map((child) => toTreeNode(child)),
        loaded: true,
        loading: false,
      }));
    } catch {
      treeData.value = cloneAndUpdate(treeData.value, nodeId, (n) => ({
        ...n,
        children: [],
        loading: false,
      }));
    }
  }

  /**
   * Toggle node expand/collapse
   * 切换节点展开/收起
   */
  async function toggleExpand(nodeId: number): Promise<void> {
    const node = findNode(treeData.value, nodeId);
    if (!node) return;

    const isCurrentlyExpanded = expandedIds.value.has(nodeId);

    // Convert to frontend tree node format / 转换为前端树节点格式且未加载，先加载
    if (node.hasChildren && !node.loaded) {
      await loadChildren(nodeId);
      // Load children on first expand / 首次展开时加载子节点完成后展开
      expandedIds.value.add(nodeId);
      expandedIds.value = new Set(expandedIds.value);
      return;
    }

    // Reload this node's info and children / 重新加载该节点的信息和子节点，切换展开/收起状态
    if (isCurrentlyExpanded) {
      expandedIds.value.delete(nodeId);
    } else {
      expandedIds.value.add(nodeId);
    }
    expandedIds.value = new Set(expandedIds.value);
  }

  /**
   * Expand all loaded nodes
   * 展开所有已加载的节点
   */
  function expandAll(): void {
    const allIds = collectAllIds(treeData.value);
    expandedIds.value = new Set(allIds);
  }

  /**
   * Collapse all nodes
   * 收起所有节点
   */
  function collapseAll(): void {
    expandedIds.value = new Set();
  }

  /**
   * Check if a node is expanded
   * 检查节点是否展开
   */
  function isExpanded(nodeId: number): boolean {
    return expandedIds.value.has(nodeId);
  }

  /**
   * Refresh entire tree
   * 刷新整棵树
   * @returns First root node
   */
  async function refresh(): Promise<null | OrgTreeNodeData> {
    // Save current expanded state
    const currentExpanded = new Set(expandedIds.value);
    const firstNode = await loadRootNodes();
    // Restore expanded state (only keep existing nodes)
    const allIds = new Set(collectAllIds(treeData.value));
    expandedIds.value = new Set(
      [...currentExpanded].filter((id) => allIds.has(id)),
    );
    return firstNode;
  }

  /**
   * Recursively delete a node (immutable version)
   */
  function cloneAndRemove(
    nodes: OrgTreeNodeData[],
    targetId: number,
  ): { removed: boolean; result: OrgTreeNodeData[] } {
    const index = nodes.findIndex((n) => n.id === targetId);
    if (index !== -1) {
      return {
        result: [...nodes.slice(0, index), ...nodes.slice(index + 1)],
        removed: true,
      };
    }
    let removed = false;
    const result = nodes.map((node) => {
      if (node.children.length > 0) {
        const childResult = cloneAndRemove(node.children, targetId);
        if (childResult.removed) {
          removed = true;
          return { ...node, children: childResult.result };
        }
      }
      return node;
    });
    return { result, removed };
  }

  /**
   * Update a single node's data
   */
  function updateNode(nodeId: number, data: Partial<OrgTreeNodeData>): void {
    treeData.value = cloneAndUpdate(treeData.value, nodeId, (n) => ({
      ...n,
      ...data,
    }));
  }

  /**
   * Delete a node
   * 删除节点
   */
  function removeNode(nodeId: number): void {
    const { result, removed } = cloneAndRemove(treeData.value, nodeId);
    if (removed) {
      expandedIds.value.delete(nodeId);
      expandedIds.value = new Set(expandedIds.value);
      treeData.value = result;
    }
  }

  /**
   * Add a node
   * 添加节点
   */
  function addNode(parentId: null | number, node: OrgTreeNodeData): void {
    treeData.value =
      parentId === null
        ? [...treeData.value, node]
        : cloneAndUpdate(treeData.value, parentId, (parent) => ({
            ...parent,
            children: [...parent.children, node],
            hasChildren: true,
            loaded: true,
          }));
  }

  // Load immediately / 立即加载
  if (immediate) {
    loadRootNodes();
  }

  return {
    treeData,
    loading,
    expandedIds,
    loadRootNodes,
    loadChildren,
    toggleExpand,
    expandAll,
    collapseAll,
    isExpanded,
    refresh,
    updateNode,
    removeNode,
    addNode,
  };
}
