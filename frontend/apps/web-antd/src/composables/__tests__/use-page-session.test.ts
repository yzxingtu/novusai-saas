import { effectScope, nextTick, ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const routePath = ref('/admin/ai/agents');

vi.mock('vue-router', () => ({
  useRoute: () => ({
    get path() {
      return routePath.value;
    },
  }),
}));

describe('usePageSession', () => {
  beforeEach(() => {
    vi.resetModules();
    routePath.value = '/admin/ai/agents';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('generates an initial page session id and refreshes it on route change', async () => {
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn().mockReturnValueOnce('uuid-1').mockReturnValueOnce('uuid-2'),
    });

    const module = await import('../use-page-session');
    const scope = effectScope();
    let state!: ReturnType<typeof module.usePageSession>;
    scope.run(() => {
      state = module.usePageSession();
    });

    expect(state.pageSessionId.value).toBe('uuid-1');
    expect(module.getActivePageSessionId()).toBe('uuid-1');

    routePath.value = '/admin/ai/models';
    await nextTick();

    expect(state.pageSessionId.value).toBe('uuid-2');
    expect(module.getActivePageSessionId()).toBe('uuid-2');
    scope.stop();
  });

  it('reuses the current session id when remounted on the same route', async () => {
    const randomUUID = vi
      .fn()
      .mockReturnValueOnce('uuid-1')
      .mockReturnValueOnce('uuid-2');
    vi.stubGlobal('crypto', { randomUUID });

    const module = await import('../use-page-session');

    const scopeA = effectScope();
    let firstState!: ReturnType<typeof module.usePageSession>;
    scopeA.run(() => {
      firstState = module.usePageSession();
    });
    scopeA.stop();

    const scopeB = effectScope();
    let secondState!: ReturnType<typeof module.usePageSession>;
    scopeB.run(() => {
      secondState = module.usePageSession();
    });

    expect(firstState.pageSessionId.value).toBe('uuid-1');
    expect(secondState.pageSessionId.value).toBe('uuid-1');
    expect(randomUUID).toHaveBeenCalledTimes(1);
    scopeB.stop();
  });
});
