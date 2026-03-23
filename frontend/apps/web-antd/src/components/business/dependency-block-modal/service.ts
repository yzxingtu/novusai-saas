import type { App, ComponentPublicInstance } from 'vue';

import { createApp, h } from 'vue';

import DependencyBlockModal from './index.vue';

export interface DependencyItem {
  id: number;
  label?: string;
}

export interface DependencyGroup {
  type: string;
  count: number;
  items: DependencyItem[];
}

export interface DeletePreviewResult {
  blocked: boolean;
  blockers: DependencyGroup[];
  cascade_soft: DependencyGroup[];
  cascade_delete: DependencyGroup[];
  nullify: DependencyGroup[];
}

interface DependencyBlockModalExposed {
  close: () => void;
  openBlocked: (deps: DependencyGroup[], name?: string) => void;
  openPreview: (preview: DeletePreviewResult, name: string) => Promise<boolean>;
}

let modalApi: DependencyBlockModalExposed | null = null;
let modalApp: App<Element> | null = null;
let modalHost: HTMLDivElement | null = null;
let modalReadyPromise: null | Promise<DependencyBlockModalExposed> = null;

async function ensureDependencyBlockModal(): Promise<DependencyBlockModalExposed> {
  if (modalApi) {
    return modalApi;
  }

  if (modalReadyPromise) {
    return modalReadyPromise;
  }

  if (typeof document === 'undefined') {
    throw new Error('DependencyBlockModal requires browser document.');
  }

  modalReadyPromise = new Promise<DependencyBlockModalExposed>((resolve) => {
    modalHost = document.createElement('div');
    modalHost.dataset.novusDependencyBlockModal = 'true';
    document.body.appendChild(modalHost);

    const Root = {
      render() {
        return h(DependencyBlockModal, {
          ref: (instance: Element | ComponentPublicInstance | null) => {
            if (!instance || instance instanceof Element) {
              return;
            }
            const exposed = instance as ComponentPublicInstance &
              DependencyBlockModalExposed;
            if (!modalApi) {
              modalApi = exposed;
              resolve(exposed);
            }
          },
        });
      },
    };

    modalApp = createApp(Root);
    modalApp.mount(modalHost);
  });

  return modalReadyPromise;
}

export async function showDependencyBlockModal(
  deps: DependencyGroup[],
  name?: string,
): Promise<void> {
  const modal = await ensureDependencyBlockModal();
  modal.openBlocked(deps, name);
}

export async function showDependencyPreviewModal(
  preview: DeletePreviewResult,
  name: string,
): Promise<boolean> {
  const modal = await ensureDependencyBlockModal();
  return modal.openPreview(preview, name);
}

export function resetDependencyBlockModalForTesting(): void {
  modalApi?.close?.();
  modalApp?.unmount();
  modalHost?.remove();
  modalApi = null;
  modalApp = null;
  modalHost = null;
  modalReadyPromise = null;
}
