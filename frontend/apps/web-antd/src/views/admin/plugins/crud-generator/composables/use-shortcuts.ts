/**
 * CRUD Generator — 键盘快捷键注册
 *
 * Ctrl+Z 撤销, Ctrl+Shift+Z 重做,
 * Ctrl+K 命令面板, Ctrl+M 切换JSON, Ctrl+I AI聊天
 */

import { onMounted, onUnmounted, ref } from 'vue';

import type { UseCrudConfigReturn } from './use-crud-config';

export interface ShortcutActions {
  toggleCommandPalette: () => void;
  toggleMode: () => void;
  openGlobalChat?: () => void;
  generate?: () => void;
  addField?: () => void;
}

export function useShortcuts(
  crudConfig: UseCrudConfigReturn,
  actions: ShortcutActions,
) {
  const commandPaletteOpen = ref(false);

  function handleKeyDown(e: KeyboardEvent) {
    const isCtrl = e.ctrlKey || e.metaKey;

    // Ctrl+K — Command Palette
    if (isCtrl && e.key === 'k') {
      e.preventDefault();
      commandPaletteOpen.value = !commandPaletteOpen.value;
      actions.toggleCommandPalette();
      return;
    }

    // Ctrl+Z — Undo
    if (isCtrl && !e.shiftKey && e.key === 'z') {
      // Only intercept if not in a text input
      if (isInTextInput(e)) return;
      e.preventDefault();
      crudConfig.undo();
      return;
    }

    // Ctrl+Shift+Z — Redo
    if (isCtrl && e.shiftKey && e.key === 'Z') {
      if (isInTextInput(e)) return;
      e.preventDefault();
      crudConfig.redo();
      return;
    }

    // Ctrl+M — Toggle Mode
    if (isCtrl && e.key === 'm') {
      e.preventDefault();
      actions.toggleMode();
      return;
    }

    // Ctrl+I — Open Global AI Chat
    if (isCtrl && e.key === 'i') {
      e.preventDefault();
      actions.openGlobalChat?.();
      return;
    }

    // Ctrl+G — Generate
    if (isCtrl && e.key === 'g') {
      e.preventDefault();
      actions.generate?.();
      return;
    }

    // Ctrl+Shift+F — Add new field
    if (isCtrl && e.shiftKey && e.key === 'F') {
      e.preventDefault();
      actions.addField?.();
    }
  }

  function isInTextInput(e: KeyboardEvent): boolean {
    const target = e.target as HTMLElement;
    if (!target) return false;
    const tag = target.tagName.toLowerCase();
    return (
      tag === 'input' ||
      tag === 'textarea' ||
      target.isContentEditable
    );
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeyDown);
  });

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown);
  });

  return {
    commandPaletteOpen,
  };
}
