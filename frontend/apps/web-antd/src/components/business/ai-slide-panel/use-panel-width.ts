import type { ComputedRef, Ref } from 'vue';

import { computed, ref } from 'vue';

type PanelMode = 'full' | 'panel';

interface PanelWidthStoreLike {
  mode: PanelMode;
  panelWidth: number;
}

const STORAGE_KEY = 'ai-slide-panel-width';
const MIN_WIDTH = 400;
const MAX_WIDTH = 800;
const DEFAULT_WIDTH = 460;

export function usePanelWidth(store: PanelWidthStoreLike): {
  dragging: Ref<boolean>;
  effectivePanelStyle: ComputedRef<{ width: string }>;
  isFullMode: ComputedRef<boolean>;
  loadSavedWidth: () => void;
  onDragStart: (event: MouseEvent) => void;
  panelWidth: Ref<number>;
} {
  const panelWidth = ref(DEFAULT_WIDTH);
  const dragging = ref(false);

  const isFullMode = computed(() => store.mode === 'full');

  const effectivePanelStyle = computed(() => ({
    width: isFullMode.value ? '100vw' : `${panelWidth.value}px`,
  }));

  function loadSavedWidth() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const width = Number.parseInt(saved, 10);
        if (width >= MIN_WIDTH && width <= MAX_WIDTH) {
          panelWidth.value = width;
        }
      }
    } catch {
      /* ignore */
    }
    store.panelWidth = panelWidth.value;
  }

  function saveWidth() {
    try {
      localStorage.setItem(STORAGE_KEY, String(panelWidth.value));
    } catch {
      /* ignore */
    }
  }

  function onDragStart(event: MouseEvent) {
    event.preventDefault();
    dragging.value = true;
    const startX = event.clientX;
    const startWidth = panelWidth.value;

    function onMouseMove(nextEvent: MouseEvent) {
      const diff = startX - nextEvent.clientX;
      panelWidth.value = Math.min(
        MAX_WIDTH,
        Math.max(MIN_WIDTH, startWidth + diff),
      );
      store.panelWidth = panelWidth.value;
    }

    function onMouseUp() {
      dragging.value = false;
      saveWidth();
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  return {
    dragging,
    effectivePanelStyle,
    isFullMode,
    loadSavedWidth,
    onDragStart,
    panelWidth,
  };
}
