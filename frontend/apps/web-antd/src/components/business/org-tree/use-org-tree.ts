import type { OrgTreeNodeData, UseOrgTreeReturn } from './types';

/**
 * 组织架构树 Hook
 * 管理树数据状态、懒加载、展开状态等
 */
import type { OrgNodeInfo } from '#/api/admin/organization';

import { ref, shallowRef } from 'vue';

import { adminApi, tenantApi } from '#/api';

export interface UseOrgTreeOptions {
  /** API 前缀 */
  apiPrefix?: 'admin' | 'tenant';
  /** 初始化时自动加载根节点 */
  immediate?: boolean;
}

/**
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
 * 组织架构树 Hook
 */
export function useOrgTree(options: UseOrgTreeOptions = {}): UseOrgTreeReturn {
  const { apiPrefix = 'admin', immediate = true } = options;

  // 获取 API
  const api =
    apiPrefix === 'admin'
      ? {
          getRootNodes: adminApi.getOrganizationRootNodesApi,
          getChildren: adminApi.getNodeChildrenApi,
        }
      : {
          getRootNodes: tenantApi.getTenantOrganizationRootNodesApi,
          getChildren: tenantApi.getTenantNodeChildrenApi,
        };

  // 状态
  const treeData = shallowRef<OrgTreeNodeData[]>([]);
  const loading = ref(false);
  const expandedIds = ref<Set<number>>(new Set());

  /**
   * 加载根节点
   * @returns 第一个根节点（用于自动选择）
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
   * 递归克隆并更新节点
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
   * 加载子节点
   */
  async function loadChildren(nodeId: number): Promise<void> {
    const node = findNode(treeData.value, nodeId);
    if (!node || node.loaded) return;

    // 设置 loading 状态
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
   * 切换展开状态
   */
  async function toggleExpand(nodeId: number): Promise<void> {
    const node = findNode(treeData.value, nodeId);
    if (!node) return;

    const isCurrentlyExpanded = expandedIds.value.has(nodeId);

    // 如果有子节点且未加载，先加载
    if (node.hasChildren && !node.loaded) {
      await loadChildren(nodeId);
      // 加载完成后展开
      expandedIds.value.add(nodeId);
      expandedIds.value = new Set(expandedIds.value);
      return;
    }

    // 已加载的节点，切换展开/收起状态
    if (isCurrentlyExpanded) {
      expandedIds.value.delete(nodeId);
    } else {
      expandedIds.value.add(nodeId);
    }
    expandedIds.value = new Set(expandedIds.value);
  }

  /**
   * 展开所有已加载的节点
   */
  function expandAll(): void {
    const allIds = collectAllIds(treeData.value);
    expandedIds.value = new Set(allIds);
  }

  /**
   * 收起所有节点
   */
  function collapseAll(): void {
    expandedIds.value = new Set();
  }

  /**
   * 检查节点是否展开
   */
  function isExpanded(nodeId: number): boolean {
    return expandedIds.value.has(nodeId);
  }

  /**
   * 刷新数据
   * @returns 第一个根节点
   */
  async function refresh(): Promise<null | OrgTreeNodeData> {
    // 保存当前展开状态
    const currentExpanded = new Set(expandedIds.value);
    const firstNode = await loadRootNodes();
    // 恢复展开状态（只保留仍存在的节点）
    const allIds = new Set(collectAllIds(treeData.value));
    expandedIds.value = new Set(
      [...currentExpanded].filter((id) => allIds.has(id)),
    );
    return firstNode;
  }

  /**
   * 递归删除节点（不可变版本）
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
   * 更新单个节点数据
   */
  function updateNode(nodeId: number, data: Partial<OrgTreeNodeData>): void {
    treeData.value = cloneAndUpdate(treeData.value, nodeId, (n) => ({
      ...n,
      ...data,
    }));
  }

  /**
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

  // 立即加载
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
