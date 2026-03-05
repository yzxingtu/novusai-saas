import type { Component } from 'vue';

import { markRaw, ref } from 'vue';

/**
 * 插件扩展注册中心 (Pinia)
 *
 * 管理插件注册的编辑器扩展、面板、命令等高级扩展点。
 * 与 plugin-slots.ts（UI 插槽）互补：
 * - plugin-slots: 固定位置的 UI 组件（header widget、floating panel 等）
 * - plugin-extensions: 可编程扩展（编辑器扩展、命令、面板注入等）
 *
 * 设计原则：
 * - 去重：同 pluginName + id 不重复注册
 * - 排序：按 priority（数字越小越优先）
 * - 冲突：同 id 不同 pluginName → 按 priority 取胜，冲突记录到 warnings
 * - 热更新：unregisterPlugin 清除该插件所有扩展，支持不刷页面的启用/禁用
 */
import { defineStore } from 'pinia';

// ── 类型定义 ──

/** 编辑器扩展声明（Tiptap Extension / ProseMirror Plugin 等） */
export interface EditorExtensionItem {
  /** 扩展唯一 ID（如 "novusdoc-pro.ai-completion"） */
  id: string;
  /** 注册插件名 */
  pluginName: string;
  /** 扩展对象（Tiptap Extension 实例或工厂函数） */
  extension: unknown;
  /** 优先级（数字越小越优先，默认 100） */
  priority?: number;
  /** 人类可读名称 */
  name?: string;
  /** 扩展分组（如 "mark", "node", "plugin", "decoration"） */
  group?: string;
}

/** 编辑器面板声明（侧边栏/底部/浮动面板） */
export interface EditorPanelItem {
  /** 面板唯一 ID */
  id: string;
  /** 注册插件名 */
  pluginName: string;
  /** Vue 组件 */
  component: Component;
  /** 面板位置: sidebar / bottom / floating */
  position: 'bottom' | 'floating' | 'sidebar';
  /** 面板标题 */
  title?: string;
  /** 面板图标（Iconify 格式） */
  icon?: string;
  /** 优先级 */
  priority?: number;
  /** 是否默认展开 */
  defaultOpen?: boolean;
}

/** 命令声明（命令面板 / 快捷键） */
export interface EditorCommandItem {
  /** 命令唯一 ID（如 "novusdoc-pro.ai-rewrite"） */
  id: string;
  /** 注册插件名 */
  pluginName: string;
  /** 命令执行函数 */
  execute: (...args: unknown[]) => unknown;
  /** 命令标题 */
  title?: string;
  /** 快捷键（如 "Ctrl+Shift+R"） */
  shortcut?: string;
  /** 命令分组 */
  group?: string;
  /** 优先级 */
  priority?: number;
}

/** 冲突警告记录 */
export interface ExtensionConflict {
  type: 'command' | 'extension' | 'panel';
  id: string;
  winner: string;
  loser: string;
  reason: string;
}

export const usePluginExtensionsStore = defineStore('plugin-extensions', () => {
  const editorExtensions = ref<EditorExtensionItem[]>([]);
  const editorPanels = ref<EditorPanelItem[]>([]);
  const editorCommands = ref<EditorCommandItem[]>([]);
  const conflicts = ref<ExtensionConflict[]>([]);

  // ── 编辑器扩展 ──

  function registerEditorExtension(item: EditorExtensionItem): boolean {
    const existing = editorExtensions.value.find((e) => e.id === item.id);
    if (existing) {
      if (existing.pluginName === item.pluginName) return false; // 重复注册
      // 冲突：按 priority 决定
      const existingPriority = existing.priority ?? 100;
      const newPriority = item.priority ?? 100;
      if (newPriority < existingPriority) {
        // 新的优先级更高，替换
        editorExtensions.value = editorExtensions.value.filter(
          (e) => e.id !== item.id,
        );
        conflicts.value.push({
          type: 'extension',
          id: item.id,
          winner: item.pluginName,
          loser: existing.pluginName,
          reason: `priority ${newPriority} < ${existingPriority}`,
        });
      } else {
        conflicts.value.push({
          type: 'extension',
          id: item.id,
          winner: existing.pluginName,
          loser: item.pluginName,
          reason: `priority ${existingPriority} <= ${newPriority}`,
        });
        return false;
      }
    }
    editorExtensions.value.push(item);
    editorExtensions.value.sort(
      (a, b) => (a.priority ?? 100) - (b.priority ?? 100),
    );
    return true;
  }

  // ── 编辑器面板 ──

  function registerEditorPanel(item: EditorPanelItem): boolean {
    const existing = editorPanels.value.find((e) => e.id === item.id);
    if (existing) {
      if (existing.pluginName === item.pluginName) return false;
      const existingPriority = existing.priority ?? 100;
      const newPriority = item.priority ?? 100;
      if (newPriority < existingPriority) {
        editorPanels.value = editorPanels.value.filter((e) => e.id !== item.id);
        conflicts.value.push({
          type: 'panel',
          id: item.id,
          winner: item.pluginName,
          loser: existing.pluginName,
          reason: `priority ${newPriority} < ${existingPriority}`,
        });
      } else {
        conflicts.value.push({
          type: 'panel',
          id: item.id,
          winner: existing.pluginName,
          loser: item.pluginName,
          reason: `priority ${existingPriority} <= ${newPriority}`,
        });
        return false;
      }
    }
    editorPanels.value.push({
      ...item,
      component: markRaw(item.component),
    });
    editorPanels.value.sort(
      (a, b) => (a.priority ?? 100) - (b.priority ?? 100),
    );
    return true;
  }

  // ── 命令 ──

  function registerCommand(item: EditorCommandItem): boolean {
    const existing = editorCommands.value.find((e) => e.id === item.id);
    if (existing) {
      if (existing.pluginName === item.pluginName) return false;
      const existingPriority = existing.priority ?? 100;
      const newPriority = item.priority ?? 100;
      if (newPriority < existingPriority) {
        editorCommands.value = editorCommands.value.filter(
          (e) => e.id !== item.id,
        );
        conflicts.value.push({
          type: 'command',
          id: item.id,
          winner: item.pluginName,
          loser: existing.pluginName,
          reason: `priority ${newPriority} < ${existingPriority}`,
        });
      } else {
        conflicts.value.push({
          type: 'command',
          id: item.id,
          winner: existing.pluginName,
          loser: item.pluginName,
          reason: `priority ${existingPriority} <= ${newPriority}`,
        });
        return false;
      }
    }
    editorCommands.value.push(item);
    editorCommands.value.sort(
      (a, b) => (a.priority ?? 100) - (b.priority ?? 100),
    );
    return true;
  }

  // ── 查询 ──

  function getExtensionsByGroup(group: string): EditorExtensionItem[] {
    return editorExtensions.value.filter((e) => e.group === group);
  }

  function getPanelsByPosition(position: string): EditorPanelItem[] {
    return editorPanels.value.filter((p) => p.position === position);
  }

  function getCommandsByGroup(group: string): EditorCommandItem[] {
    return editorCommands.value.filter((c) => c.group === group);
  }

  function executeCommand(id: string, ...args: unknown[]): unknown {
    const cmd = editorCommands.value.find((c) => c.id === id);
    if (!cmd) {
      console.warn(`[PluginExtensions] Command '${id}' not found`);
      return undefined;
    }
    return cmd.execute(...args);
  }

  // ── 生命周期 ──

  function unregisterPlugin(pluginName: string) {
    editorExtensions.value = editorExtensions.value.filter(
      (e) => e.pluginName !== pluginName,
    );
    editorPanels.value = editorPanels.value.filter(
      (p) => p.pluginName !== pluginName,
    );
    editorCommands.value = editorCommands.value.filter(
      (c) => c.pluginName !== pluginName,
    );
    conflicts.value = conflicts.value.filter(
      (c) => c.winner !== pluginName && c.loser !== pluginName,
    );
  }

  function clearAll() {
    editorExtensions.value = [];
    editorPanels.value = [];
    editorCommands.value = [];
    conflicts.value = [];
  }

  return {
    // state
    editorExtensions,
    editorPanels,
    editorCommands,
    conflicts,
    // register
    registerEditorExtension,
    registerEditorPanel,
    registerCommand,
    // query
    getExtensionsByGroup,
    getPanelsByPosition,
    getCommandsByGroup,
    executeCommand,
    // lifecycle
    unregisterPlugin,
    clearAll,
  };
});
