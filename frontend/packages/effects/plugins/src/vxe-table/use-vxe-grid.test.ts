/* eslint-disable vue/one-component-per-file */
import { mount } from '@vue/test-utils';
import { computed, defineComponent, h, nextTick, ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useVbenVxeGrid } from './use-vxe-grid';

const mockRefs = vi.hoisted(() => {
  const recalculate = vi.fn();
  const setState = vi.fn();
  const getValues = vi.fn(async () => ({}));
  const getLatestSubmissionValues = vi.fn(() => ({}));
  const resetForm = vi.fn(async () => undefined);
  const setLatestSubmissionValues = vi.fn();
  const formState = {
    compact: true,
  };

  return {
    formState,
    formApi: {
      getLatestSubmissionValues,
      getState: vi.fn(() => formState),
      getValues,
      resetForm,
      setLatestSubmissionValues,
      setState,
      unmount: vi.fn(),
    },
    recalculate,
  };
});

vi.mock('@vben/hooks', () => ({
  usePriorityValues: (props: Record<string, unknown>, state: any) =>
    new Proxy(
      {},
      {
        get(_, key: string) {
          return computed(() => {
            const stateValue = state?.value?.[key];
            if (stateValue === undefined) {
              return props[key];
            }
            return stateValue;
          });
        },
      },
    ),
}));

vi.mock('@vben/icons', () => ({
  EmptyIcon: defineComponent({
    name: 'MockEmptyIcon',
    render: () => h('div', { 'data-test': 'empty-icon' }),
  }),
}));

vi.mock('@vben/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/preferences', () => ({
  usePreferences: () => ({
    isMobile: ref(false),
  }),
}));

vi.mock('@vben-core/shadcn-ui', () => ({
  VbenHelpTooltip: defineComponent({
    name: 'MockHelpTooltip',
    render() {
      return this.$slots.default?.();
    },
  }),
  VbenLoading: defineComponent({
    name: 'MockLoading',
    render: () => h('div', { 'data-test': 'loading' }),
  }),
}));

vi.mock('vxe-pc-ui', () => ({
  VxeButton: defineComponent({
    name: 'MockVxeButton',
    props: {
      title: {
        default: '',
        type: String,
      },
    },
    emits: ['click'],
    setup(props, { emit }) {
      return () =>
        h(
          'button',
          {
            title: props.title,
            type: 'button',
            onClick: () => emit('click'),
          },
          'search',
        );
    },
  }),
}));

vi.mock('vxe-table', () => ({
  VxeGrid: defineComponent({
    name: 'MockVxeGrid',
    setup(_, { expose, slots }) {
      expose({
        commitProxy: vi.fn(),
        recalculate: mockRefs.recalculate,
      });
      return () =>
        h('div', { 'data-test': 'mock-grid' }, [
          slots['toolbar-actions']?.({}),
          slots['toolbar-tools']?.({}),
          slots.form?.({}),
          slots.loading?.({}),
          slots.empty?.({}),
        ]);
    },
  }),
  VxeUI: {
    getConfig: () => ({ grid: {} }),
  },
}));

vi.mock('./extends', () => ({
  extendProxyOptions: vi.fn(),
}));

vi.mock('./init', () => ({
  useTableForm: () => [
    defineComponent({
      name: 'MockSearchForm',
      render: () => h('div', { 'data-test': 'mock-form' }),
    }),
    mockRefs.formApi,
  ],
}));

function createHarness(options: Record<string, unknown>) {
  return defineComponent({
    name: 'UseVxeGridHarness',
    setup() {
      const [Grid] = useVbenVxeGrid(options as any);
      return () => h(Grid);
    },
  });
}

function getSearchPanelElements(wrapper: ReturnType<typeof mount>) {
  const formRoot = wrapper.get('[data-test="mock-form"]')
    .element as HTMLElement;
  const body = formRoot.parentElement as HTMLElement;
  const shell = body.parentElement?.parentElement as HTMLElement;

  return {
    body,
    shell,
  };
}

describe('use-vxe-grid search panel', () => {
  beforeEach(() => {
    mockRefs.recalculate.mockReset();
    mockRefs.formApi.getLatestSubmissionValues.mockReset();
    mockRefs.formApi.getState.mockClear();
    mockRefs.formApi.getValues.mockReset();
    mockRefs.formApi.resetForm.mockReset();
    mockRefs.formApi.setLatestSubmissionValues.mockReset();
    mockRefs.formApi.setState.mockReset();
    mockRefs.formApi.unmount.mockReset();
    mockRefs.formState.compact = true;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('uses lightweight content animation by default without layout transition', async () => {
    vi.useFakeTimers();

    const wrapper = mount(
      createHarness({
        formOptions: {
          schema: [],
        },
        gridOptions: {
          toolbarConfig: {
            search: true,
          },
        },
        showSearchForm: true,
      }),
    );

    const { body, shell } = getSearchPanelElements(wrapper);
    expect(shell.getAttribute('style')).toContain('display: block');
    expect(shell.getAttribute('style')).not.toContain('grid-template-rows');
    expect(body.className).toContain('vxe-grid-search-panel');
    expect(body.className).toContain('is-modern-motion');
    expect(body.className).toContain('is-visible');
    expect(body.getAttribute('style')).toContain(
      '--vxe-search-panel-motion-duration: 220ms',
    );

    await wrapper
      .get('button[title="common.hideSearchPanel"]')
      .trigger('click');
    await nextTick();

    expect(shell.getAttribute('style')).toContain('display: block');
    expect(body.className).toContain('is-hidden');
    expect(mockRefs.recalculate).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(250);
    await nextTick();

    expect(shell.getAttribute('style')).toContain('display: none');
    expect(mockRefs.recalculate).toHaveBeenCalledTimes(1);

    await wrapper
      .get('button[title="common.showSearchPanel"]')
      .trigger('click');
    await nextTick();
    await nextTick();

    expect(shell.getAttribute('style')).toContain('display: block');
    expect(shell.getAttribute('style')).not.toContain('grid-template-rows');
    expect(body.className).toContain('is-visible');
    expect(mockRefs.recalculate).toHaveBeenCalledTimes(2);
  });

  it('keeps the legacy transition when search panel animation is enabled', async () => {
    vi.useFakeTimers();

    const wrapper = mount(
      createHarness({
        formOptions: {
          schema: [],
        },
        gridOptions: {
          toolbarConfig: {
            search: true,
          },
        },
        searchPanelAnimation: true,
        showSearchForm: true,
      }),
    );

    const { shell } = getSearchPanelElements(wrapper);
    const { body } = getSearchPanelElements(wrapper);
    expect(shell.getAttribute('style')).toContain('display: grid');
    expect(shell.getAttribute('style')).toContain('grid-template-rows: 1fr');
    expect(shell.getAttribute('style')).toContain(
      'transition: grid-template-rows 240ms',
    );
    expect(body.className).toContain('is-legacy-motion');

    await wrapper
      .get('button[title="common.hideSearchPanel"]')
      .trigger('click');
    await nextTick();

    expect(shell.getAttribute('style')).toContain('grid-template-rows: 0fr');
    expect(mockRefs.recalculate).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(300);
    await nextTick();

    expect(mockRefs.recalculate).toHaveBeenCalledTimes(1);
  });
});
