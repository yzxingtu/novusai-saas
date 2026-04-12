// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent, h, ref } from 'vue';

import SystemLogToolbar from '../components/SystemLogToolbar.vue';

type SystemLogFile = {
  filename: string;
  isCurrent?: boolean;
};

type SystemLogCategory = {
  code: string;
  name: string;
};

function createContext() {
  return {
    activeCategoryMeta: ref<SystemLogCategory | null>(null),
    downloadingFile: ref<null | string>(null),
    getCategoryVisual: vi.fn(() => ({
      icon: 'lucide:file-code-2',
      badge: 'badge',
      activeCard: '',
      iconWrap: '',
    })),
    getPillButtonClass: vi.fn(() => 'pill'),
    logContent: ref<null | { lines: string[] }>(null),
    onCopyAll: vi.fn(),
    onDownload: vi.fn(),
    onRefresh: vi.fn(),
    selectedFile: ref<SystemLogFile | null>(null),
    statsLoading: ref(false),
    toolbarMetrics: ref([
      {
        key: 'total-files',
        labelKey: 'admin.system.systemLog.totalFiles',
        value: '0',
      },
    ]),
  };
}

const contextState = {
  current: createContext(),
};

vi.mock('../composables/useSystemLogs', () => ({
  useSystemLogsContext: () => contextState.current,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    props: {
      icon: {
        default: '',
        type: String,
      },
    },
    setup(props) {
      return () => h('span', { 'data-icon': props.icon });
    },
  }),
}));

vi.mock('ant-design-vue', () => ({
  Spin: defineComponent({
    name: 'SpinStub',
    props: {
      spinning: {
        default: false,
        type: Boolean,
      },
    },
    setup(props, { slots }) {
      return () =>
        h('div', { 'data-spinning': String(props.spinning) }, slots.default?.());
    },
  }),
}));

beforeEach(() => {
  contextState.current = createContext();
});

describe('SystemLogToolbar slice', () => {
  it('renders chips for file, category, and live status', () => {
    contextState.current.selectedFile.value = {
      filename: 'app.log',
      isCurrent: true,
    };
    contextState.current.activeCategoryMeta.value = {
      code: 'app',
      name: 'Application',
    };

    const wrapper = mount(SystemLogToolbar);

    expect(wrapper.text()).toContain('app.log');
    expect(wrapper.text()).toContain(
      'admin.system.systemLog.category: Application',
    );
    expect(wrapper.text()).toContain('admin.system.systemLog.running');
  });

  it('disables download and copy buttons when no selection or content', () => {
    const wrapper = mount(SystemLogToolbar);

    const buttons = wrapper.findAll('button');
    const downloadButton = buttons.find((button) =>
      button.text().includes('admin.system.systemLog.download'),
    );
    const copyButton = buttons.find((button) =>
      button.text().includes('admin.system.systemLog.copyAll'),
    );

    if (!downloadButton || !copyButton) {
      throw new Error('Toolbar action buttons missing');
    }

    expect((downloadButton.element as HTMLButtonElement).disabled).toBe(true);
    expect((copyButton.element as HTMLButtonElement).disabled).toBe(true);
  });
});
