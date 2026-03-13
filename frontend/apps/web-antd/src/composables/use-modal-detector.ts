/**
 * Modal/Drawer Detector
 * 弹窗/抽屉检测器
 *
 * Uses MutationObserver to detect Ant Design modals and drawers opening/closing.
 * Provides structured state (type, title, visible) for AI page awareness.
 * 使用 MutationObserver 检测 Ant Design 弹窗和抽屉的打开/关闭。
 * 为 AI 页面感知提供结构化状态（类型、标题、可见性）。
 */

import { onMounted, onUnmounted, ref, type Ref } from 'vue';

export interface ModalDetection {
  type: 'drawer' | 'modal';
  title: string;
  visible: boolean;
}

interface UseModalDetectorReturn {
  /** Currently detected modals/drawers */
  modalState: Ref<ModalDetection[]>;
  /** Force an immediate scan */
  scan: () => void;
}

const DEBOUNCE_MS = 150;

/**
 * Composable that automatically detects Ant Design modals and drawers via MutationObserver.
 * Must be called inside a component setup function.
 */
export function useModalDetector(): UseModalDetectorReturn {
  const modalState = ref<ModalDetection[]>([]);
  let observer: MutationObserver | null = null;
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  function scan() {
    const results: ModalDetection[] = [];

    const modals = document.querySelectorAll(
      '.ant-modal-wrap:not(.ant-modal-wrap-hidden)',
    );
    modals.forEach((el) => {
      const title =
        el.querySelector('.ant-modal-title')?.textContent?.trim() || '';
      results.push({ type: 'modal', title: title || 'Untitled', visible: true });
    });

    const drawers = document.querySelectorAll('.ant-drawer-open');
    drawers.forEach((el) => {
      const title =
        el.querySelector('.ant-drawer-title')?.textContent?.trim() || '';
      results.push({ type: 'drawer', title: title || 'Untitled', visible: true });
    });

    modalState.value = results;
  }

  function debouncedScan() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(scan, DEBOUNCE_MS);
  }

  onMounted(() => {
    observer = new MutationObserver(debouncedScan);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'style'],
    });
    scan();
  });

  onUnmounted(() => {
    observer?.disconnect();
    observer = null;
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
  });

  return { modalState, scan };
}
