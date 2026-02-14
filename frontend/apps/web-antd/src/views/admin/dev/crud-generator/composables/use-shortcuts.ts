/**
 * CRUD Generator — 键盘快捷键注册
 *
 * Ctrl+Z 撤销, Ctrl+Shift+Z 重做, Ctrl+Enter 下一步,
 * Ctrl+K 命令面板, Ctrl+P 预览, Ctrl+G 生成
 */

import { onMounted, onUnmounted, ref } from 'vue';

import type { UseCrudConfigReturn } from './use-crud-config';

export interface ShortcutActions {
  toggleCommandPalette: () => void;
  toggleMode: () => void;
  openAiAssistant?: () => void;
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

    // Ctrl+Enter — Next Step
    if (isCtrl && e.key === 'Enter') {
      e.preventDefault();
      crudConfig.nextStep();
      return;
    }

    // Ctrl+P — Jump to Preview (Step 4)
    if (isCtrl && e.key === 'p') {
      e.preventDefault();
      crudConfig.goToStep(4);
      return;
    }

    // Ctrl+M — Toggle Mode
    if (isCtrl && e.key === 'm') {
      e.preventDefault();
      actions.toggleMode();
      return;
    }

    // Ctrl+I — Open AI Assistant
    if (isCtrl && e.key === 'i') {
      e.preventDefault();
      actions.openAiAssistant?.();
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
