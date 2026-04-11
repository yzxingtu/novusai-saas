import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const storageMock: Storage = {
  getItem: () => null,
  key: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
  clear: () => undefined,
  length: 0,
};

vi.stubGlobal('window', {
  localStorage: storageMock,
  sessionStorage: storageMock,
} as Window);
vi.stubGlobal('localStorage', storageMock);

describe('useCodegenBuilderStore', () => {
  let getStore: typeof import('../codegen-builder').useCodegenBuilderStore;

  beforeEach(async () => {
    setActivePinia(createPinia());
    const module = await import('../codegen-builder');
    getStore = module.useCodegenBuilderStore;
  });

  it('survives structuredClone failures', () => {
    const store = getStore();
    const nonCloneable = { fn: () => {} };

    const payload = { recursive: nonCloneable };
    expect(() => store.updateConfig(payload)).not.toThrow();
    expect(store.$state.historyStack.length).toBeGreaterThan(0);
    expect(store.$state.configJson.recursive).toStrictEqual(payload.recursive);
  });
});
