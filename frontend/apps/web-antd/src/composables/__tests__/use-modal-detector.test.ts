// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { useModalDetector } from '../use-modal-detector';

function mountHarness() {
  const wrapper = mount(
    defineComponent({
      setup() {
        return useModalDetector();
      },
      render: () => null,
    }),
  );

  return wrapper.vm as unknown as {
    modalState: Array<{ title: string; type: 'drawer' | 'modal'; visible: boolean }>;
    scan: () => void;
  };
}

describe('useModalDetector', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('detects visible modal and drawer titles on mount', async () => {
    document.body.innerHTML = `
      <div class="ant-modal-wrap">
        <div class="ant-modal-title">Edit Item</div>
      </div>
      <div class="ant-drawer-open">
        <div class="ant-drawer-title">Drawer Item</div>
      </div>
    `;

    const vm = mountHarness();
    await nextTick();

    expect(vm.modalState).toEqual([
      { type: 'modal', title: 'Edit Item', visible: true },
      { type: 'drawer', title: 'Drawer Item', visible: true },
    ]);
  });

  it('falls back to Untitled and can rescan after DOM changes', async () => {
    document.body.innerHTML = `
      <div class="ant-modal-wrap">
        <div class="ant-modal-title"></div>
      </div>
    `;

    const vm = mountHarness();
    await nextTick();

    expect(vm.modalState).toEqual([
      { type: 'modal', title: 'Untitled', visible: true },
    ]);

    document.body.innerHTML = '';
    vm.scan();

    expect(vm.modalState).toEqual([]);
  });
});
