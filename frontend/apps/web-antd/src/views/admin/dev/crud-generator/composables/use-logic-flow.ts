/**
 * Logic Flow — 可视化业务逻辑编排
 *
 * 定义 9 种节点类型及其配置结构。
 * 管理 LogicFlow JSON 状态（节点 + 连线）。
 * 将 LogicFlow 翻译为 Python 代码片段。
 *
 * 依赖: @vue-flow/core (需要安装后才能使用可视化编辑器)
 */

import { computed, ref } from 'vue';

import type { LogicFlow, LogicNode } from '../types';

// ============================================================
// Node type definitions
// ============================================================

export type LogicNodeType =
  | 'assign'
  | 'call_service'
  | 'compute'
  | 'condition'
  | 'exception'
  | 'log'
  | 'notify'
  | 'query'
  | 'validate';

export interface NodeTypeDefinition {
  type: LogicNodeType;
  label: string;
  icon: string;
  color: string;
  description: string;
  configFields: { key: string; label: string; type: 'boolean' | 'select' | 'text' | 'textarea' }[];
}

export const NODE_TYPE_REGISTRY: Record<LogicNodeType, NodeTypeDefinition> = {
  validate: {
    type: 'validate',
    label: 'Validate',
    icon: 'icon-[lucide--shield-check]',
    color: '#52c41a',
    description: 'Field validation with custom rules',
    configFields: [
      { key: 'field', label: 'Field', type: 'text' },
      { key: 'rule', label: 'Rule', type: 'select' },
      { key: 'message', label: 'Error Message', type: 'text' },
    ],
  },
  compute: {
    type: 'compute',
    label: 'Compute',
    icon: 'icon-[lucide--calculator]',
    color: '#1677ff',
    description: 'Calculate field values',
    configFields: [
      { key: 'target_field', label: 'Target Field', type: 'text' },
      { key: 'expression', label: 'Expression', type: 'textarea' },
    ],
  },
  assign: {
    type: 'assign',
    label: 'Assign',
    icon: 'icon-[lucide--pen-line]',
    color: '#722ed1',
    description: 'Set field values',
    configFields: [
      { key: 'target_field', label: 'Target Field', type: 'text' },
      { key: 'value', label: 'Value', type: 'text' },
    ],
  },
  condition: {
    type: 'condition',
    label: 'Condition',
    icon: 'icon-[lucide--git-branch]',
    color: '#fa8c16',
    description: 'Conditional branching',
    configFields: [
      { key: 'expression', label: 'Condition', type: 'textarea' },
      { key: 'true_branch', label: 'True Branch', type: 'text' },
      { key: 'false_branch', label: 'False Branch', type: 'text' },
    ],
  },
  exception: {
    type: 'exception',
    label: 'Exception',
    icon: 'icon-[lucide--alert-triangle]',
    color: '#ff4d4f',
    description: 'Throw business exception',
    configFields: [
      { key: 'exception_type', label: 'Type', type: 'select' },
      { key: 'message', label: 'Message', type: 'text' },
      { key: 'code', label: 'Error Code', type: 'text' },
    ],
  },
  notify: {
    type: 'notify',
    label: 'Notify',
    icon: 'icon-[lucide--bell]',
    color: '#13c2c2',
    description: 'Send notification (Celery task)',
    configFields: [
      { key: 'channel', label: 'Channel', type: 'select' },
      { key: 'template', label: 'Template', type: 'text' },
      { key: 'recipients', label: 'Recipients', type: 'text' },
    ],
  },
  log: {
    type: 'log',
    label: 'Log',
    icon: 'icon-[lucide--file-text]',
    color: '#8c8c8c',
    description: 'Write audit log',
    configFields: [
      { key: 'level', label: 'Level', type: 'select' },
      { key: 'message', label: 'Message', type: 'textarea' },
    ],
  },
  query: {
    type: 'query',
    label: 'Query',
    icon: 'icon-[lucide--database]',
    color: '#2f54eb',
    description: 'Query related data',
    configFields: [
      { key: 'model', label: 'Model', type: 'text' },
      { key: 'filter', label: 'Filter', type: 'textarea' },
      { key: 'result_var', label: 'Result Variable', type: 'text' },
    ],
  },
  call_service: {
    type: 'call_service',
    label: 'Call Service',
    icon: 'icon-[lucide--plug]',
    color: '#eb2f96',
    description: 'Call another service method',
    configFields: [
      { key: 'service', label: 'Service', type: 'text' },
      { key: 'method', label: 'Method', type: 'text' },
      { key: 'params', label: 'Parameters', type: 'textarea' },
    ],
  },
};

// ============================================================
// Logic Flow composable
// ============================================================

let nodeCounter = 0;

function generateNodeId(): string {
  nodeCounter++;
  return `node_${nodeCounter}`;
}

export function useLogicFlow() {
  const flows = ref<LogicFlow[]>([]);
  const activeFlowIndex = ref(0);

  const activeFlow = computed(() => flows.value[activeFlowIndex.value] ?? null);

  function addFlow(hook: string, description: string) {
    const flow: LogicFlow = {
      hook,
      nodes: [],
      entry_node_id: null,
      description,
    };
    flows.value.push(flow);
    activeFlowIndex.value = flows.value.length - 1;
  }

  function removeFlow(index: number) {
    flows.value.splice(index, 1);
    if (activeFlowIndex.value >= flows.value.length) {
      activeFlowIndex.value = Math.max(0, flows.value.length - 1);
    }
  }

  function addNode(type: LogicNodeType, config?: Record<string, unknown>): LogicNode | null {
    if (!activeFlow.value) return null;
    const id = generateNodeId();
    const node: LogicNode = {
      id,
      type,
      label: NODE_TYPE_REGISTRY[type].label,
      config: config || {},
      next_nodes: [],
      condition_branches: type === 'condition' ? {} : null,
    };
    activeFlow.value.nodes.push(node);

    if (!activeFlow.value.entry_node_id) {
      activeFlow.value.entry_node_id = id;
    }

    return node;
  }

  function removeNode(nodeId: string) {
    if (!activeFlow.value) return;
    activeFlow.value.nodes = activeFlow.value.nodes.filter((n) => n.id !== nodeId);

    for (const node of activeFlow.value.nodes) {
      node.next_nodes = node.next_nodes.filter((id) => id !== nodeId);
      if (node.condition_branches) {
        for (const [key, target] of Object.entries(node.condition_branches)) {
          if (target === nodeId) {
            delete node.condition_branches[key];
          }
        }
      }
    }

    if (activeFlow.value.entry_node_id === nodeId) {
      activeFlow.value.entry_node_id = activeFlow.value.nodes[0]?.id ?? null;
    }
  }

  function updateNodeConfig(nodeId: string, config: Record<string, unknown>) {
    if (!activeFlow.value) return;
    const node = activeFlow.value.nodes.find((n) => n.id === nodeId);
    if (node) {
      node.config = { ...node.config, ...config };
    }
  }

  function connectNodes(fromId: string, toId: string, branch?: string) {
    if (!activeFlow.value) return;
    const fromNode = activeFlow.value.nodes.find((n) => n.id === fromId);
    if (!fromNode) return;

    if (branch && fromNode.condition_branches) {
      fromNode.condition_branches[branch] = toId;
    } else if (!fromNode.next_nodes.includes(toId)) {
      fromNode.next_nodes.push(toId);
    }
  }

  function disconnectNodes(fromId: string, toId: string) {
    if (!activeFlow.value) return;
    const fromNode = activeFlow.value.nodes.find((n) => n.id === fromId);
    if (!fromNode) return;

    fromNode.next_nodes = fromNode.next_nodes.filter((id) => id !== toId);
    if (fromNode.condition_branches) {
      for (const [key, target] of Object.entries(fromNode.condition_branches)) {
        if (target === toId) {
          delete fromNode.condition_branches[key];
        }
      }
    }
  }

  return {
    flows,
    activeFlowIndex,
    activeFlow,
    addFlow,
    removeFlow,
    addNode,
    removeNode,
    updateNodeConfig,
    connectNodes,
    disconnectNodes,
  };
}

// ============================================================
// Python code generation from LogicFlow
// ============================================================

export function logicFlowToPython(flow: LogicFlow, indent: number = 2): string {
  const pad = ' '.repeat(indent);
  const lines: string[] = [];

  lines.push(`${pad}# --- Logic Flow: ${flow.hook} ---`);
  lines.push(`${pad}# ${flow.description}`);

  if (!flow.entry_node_id || flow.nodes.length === 0) {
    lines.push(`${pad}pass`);
    return lines.join('\n');
  }

  const visited = new Set<string>();

  function emitNode(nodeId: string, depth: number) {
    if (visited.has(nodeId)) return;
    visited.add(nodeId);

    const node = flow.nodes.find((n) => n.id === nodeId);
    if (!node) return;

    const p = pad + '    '.repeat(depth);

    switch (node.type) {
      case 'validate': {
        const field = node.config.field || 'field';
        const message = node.config.message || 'Validation failed';
        lines.push(`${p}if not self._validate_${field}(data.get("${field}")):`);
        lines.push(`${p}    raise ValidationException("${message}")`);
        break;
      }
      case 'compute': {
        const target = node.config.target_field || 'result';
        const expr = node.config.expression || '0';
        lines.push(`${p}data["${target}"] = ${expr}`);
        break;
      }
      case 'assign': {
        const target = node.config.target_field || 'field';
        const value = node.config.value || 'None';
        lines.push(`${p}data["${target}"] = ${value}`);
        break;
      }
      case 'condition': {
        const expr = node.config.expression || 'True';
        lines.push(`${p}if ${expr}:`);
        if (node.condition_branches?.true) {
          emitNode(node.condition_branches.true, depth + 1);
        } else {
          lines.push(`${p}    pass`);
        }
        lines.push(`${p}else:`);
        if (node.condition_branches?.false) {
          emitNode(node.condition_branches.false, depth + 1);
        } else {
          lines.push(`${p}    pass`);
        }
        break;
      }
      case 'exception': {
        const excType = node.config.exception_type || 'BusinessException';
        const message = node.config.message || 'Error';
        lines.push(`${p}raise ${excType}("${message}")`);
        break;
      }
      case 'notify': {
        const channel = node.config.channel || 'email';
        const template = node.config.template || 'default';
        lines.push(`${p}# Send notification via ${channel}`);
        lines.push(`${p}send_notification.delay(channel="${channel}", template="${template}", data=data)`);
        break;
      }
      case 'log': {
        const level = node.config.level || 'info';
        const message = node.config.message || 'Log message';
        lines.push(`${p}logger.${level}("${message}", extra={"data": data})`);
        break;
      }
      case 'query': {
        const model = node.config.model || 'Model';
        const resultVar = node.config.result_var || 'result';
        const filter = node.config.filter || '';
        lines.push(`${p}${resultVar} = await self.repo.query(${model}, ${filter || '{}'})`);
        break;
      }
      case 'call_service': {
        const service = node.config.service || 'other_service';
        const method = node.config.method || 'method';
        lines.push(`${p}await ${service}.${method}(data)`);
        break;
      }
    }

    for (const nextId of node.next_nodes) {
      emitNode(nextId, depth);
    }
  }

  emitNode(flow.entry_node_id, 0);
  return lines.join('\n');
}
