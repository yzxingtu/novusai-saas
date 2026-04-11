// @vitest-environment happy-dom

import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent, h, nextTick, ref } from 'vue';

import FilePicker from '../FilePicker.vue';

type UploadTask = {
  uid: string;
  name: string;
  file: { type: string };
  size: number;
  percent: number;
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
};

const ModalStub = defineComponent({
  name: 'ModalStub',
  props: {
    title: {
      default: '',
      type: String,
    },
  },
  setup(_, { slots }) {
    return () => h('div', { 'data-testid': 'modal' }, slots.default?.());
  },
});

const buildCoreState = () => ({
  Modal: ModalStub,
  cancelTask: vi.fn(),
  categoryFilter: ref(''),
  categoryOptions: ref([]),
  clearCompletedTasks: vi.fn(),
  clearErrors: vi.fn(),
  currentPage: ref(1),
  effectiveMaxFileSize: ref(1024),
  errorCount: ref(0),
  files: ref([]),
  getPreviewUrl: vi.fn(() => ''),
  handleCategoryChange: vi.fn(),
  handleConfirm: vi.fn(),
  handleCustomUpload: vi.fn(),
  handleFileClick: vi.fn(),
  handlePageChange: vi.fn(),
  handleSearch: vi.fn(),
  isDragOver: ref(false),
  isImage: vi.fn(() => false),
  loading: ref(false),
  modalApi: {
    close: vi.fn(),
    open: vi.fn(),
  },
  onModalDragEnter: vi.fn(),
  onModalDragLeave: vi.fn(),
  onModalDragOver: vi.fn(),
  onModalDrop: vi.fn(),
  openPreview: vi.fn(),
  pageSize: ref(18),
  previewUrl: ref(''),
  previewVisible: ref(false),
  retryAllErrors: vi.fn(),
  retryTask: vi.fn(),
  searchKeyword: ref(''),
  selectedIds: ref(new Set<number>()),
  showCategoryFilter: ref(false),
  total: ref(0),
  uploadTasks: ref<UploadTask[]>([]),
  uploadingCount: ref(0),
  viewMode: ref<'grid' | 'list'>('grid'),
});

type FilePickerCoreState = ReturnType<typeof buildCoreState>;

const createCoreState = (
  overrides: Partial<FilePickerCoreState> = {},
): FilePickerCoreState => ({
  ...buildCoreState(),
  ...overrides,
});

const coreState = {
  current: createCoreState(),
};

const mountFilePicker = (options: Parameters<typeof mount>[1] = {}) =>
  mount(FilePicker, {
    ...options,
    global: {
      ...options.global,
      mocks: {
        $t: (key: string) => key,
        ...options.global?.mocks,
      },
    },
  });

vi.mock('../use-file-picker-core', () => ({
  useFilePickerCore: () => coreState.current,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/common', () => ({
  formatDate: () => '2026-01-01',
}));

vi.mock('#/utils/file', () => ({
  formatFileSize: () => '1MB',
  getFileIcon: () => 'file-icon',
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

vi.mock('ant-design-vue', () => {
  const Button = defineComponent({
    name: 'ButtonStub',
    props: {
      disabled: {
        default: false,
        type: Boolean,
      },
    },
    setup(props, { slots }) {
      return () => h('button', { disabled: props.disabled }, slots.default?.());
    },
  });

  const Checkbox = defineComponent({
    name: 'CheckboxStub',
    props: {
      checked: {
        default: false,
        type: Boolean,
      },
    },
    setup(props) {
      return () =>
        h('input', {
          checked: props.checked,
          type: 'checkbox',
        });
    },
  });

  const Input = defineComponent({
    name: 'InputStub',
    props: {
      value: {
        default: '',
        type: String,
      },
      placeholder: {
        default: '',
        type: String,
      },
    },
    setup(props, { slots }) {
      return () =>
        h('label', [
          slots.prefix?.(),
          h('input', { placeholder: props.placeholder, value: props.value }),
        ]);
    },
  });

  const Select = defineComponent({
    name: 'SelectStub',
    props: {
      value: {
        default: '',
        type: String,
      },
      options: {
        default: () => [],
        type: Array,
      },
    },
    setup(props) {
      return () =>
        h(
          'select',
          { value: props.value },
          (props.options as Array<{ label?: string; value?: string }>).map(
            (option) =>
              h(
                'option',
                { value: option.value ?? option.label ?? '' },
                option.label ?? option.value ?? '',
              ),
          ),
        );
    },
  });

  const Pagination = defineComponent({
    name: 'PaginationStub',
    setup() {
      return () => h('div', { 'data-testid': 'pagination' });
    },
  });

  const Progress = defineComponent({
    name: 'ProgressStub',
    props: {
      percent: {
        default: 0,
        type: Number,
      },
    },
    setup(props) {
      return () =>
        h('div', { 'data-percent': String(props.percent) });
    },
  });

  const Row = defineComponent({
    name: 'RowStub',
    setup(_, { slots }) {
      return () => h('div', slots.default?.());
    },
  });

  const Col = defineComponent({
    name: 'ColStub',
    setup(_, { slots }) {
      return () => h('div', slots.default?.());
    },
  });

  const Spin = defineComponent({
    name: 'SpinStub',
    setup(_, { slots }) {
      return () => h('div', slots.default?.());
    },
  });

  const Tag = defineComponent({
    name: 'TagStub',
    setup(_, { slots }) {
      return () => h('span', slots.default?.());
    },
  });

  const Tooltip = defineComponent({
    name: 'TooltipStub',
    setup(_, { slots }) {
      return () => h('span', slots.default?.());
    },
  });

  const Image = defineComponent({
    name: 'ImageStub',
    props: {
      src: {
        default: '',
        type: String,
      },
      alt: {
        default: '',
        type: String,
      },
    },
    setup(props) {
      return () => h('img', { alt: props.alt, src: props.src });
    },
  });

  const UploadDragger = defineComponent({
    name: 'UploadDraggerStub',
    setup(_, { slots }) {
      return () => h('div', { 'data-testid': 'upload-dragger' }, slots.default?.());
    },
  });

  return {
    Button,
    Checkbox,
    Col,
    Image,
    Input,
    Pagination,
    Progress,
    Row,
    Select,
    Spin,
    Tag,
    Tooltip,
    Upload: {
      Dragger: UploadDragger,
    },
  };
});

describe('FilePicker shell slice', () => {
  beforeEach(() => {
    coreState.current = createCoreState();
  });

  it('toggles drag overlay visibility from isDragOver', async () => {
    const dragState = ref(true);
    coreState.current = createCoreState({
      isDragOver: dragState,
    });

    const wrapper = mountFilePicker();

    expect(wrapper.text()).toContain('shared.filePicker.releaseToUpload');

    dragState.value = false;
    await nextTick();

    expect(wrapper.text()).not.toContain('shared.filePicker.releaseToUpload');
  });

  it('renders upload queue only when tasks exist', async () => {
    const uploadTasks = ref<UploadTask[]>([
      {
        uid: 'u-1',
        name: 'draft.png',
        file: { type: 'image/png' },
        size: 128,
        percent: 38,
        status: 'uploading',
      },
    ]);

    coreState.current = createCoreState({
      uploadTasks,
      uploadingCount: ref(1),
    });

    const wrapper = mountFilePicker();

    expect(wrapper.text()).toContain('shared.filePicker.uploadingTitle');
    expect(wrapper.text()).toContain('draft.png');

    uploadTasks.value = [];
    coreState.current.uploadingCount.value = 0;
    await nextTick();

    expect(wrapper.text()).not.toContain('shared.filePicker.uploadingTitle');
  });

  it('enables confirm button when selection exists in multi-select mode', async () => {
    const selectedIds = ref(new Set<number>());
    coreState.current = createCoreState({
      selectedIds,
    });

    const wrapper = mountFilePicker({
      props: {
        multiple: true,
      },
    });

    const getConfirmButton = () =>
      wrapper
        .findAll('button')
        .find((button) =>
          button.text().includes('shared.common.select'),
        );

    const confirmButton = getConfirmButton();
    if (!confirmButton) {
      throw new Error('Confirm button not found');
    }
    expect((confirmButton.element as HTMLButtonElement).disabled).toBe(true);

    selectedIds.value = new Set([1]);
    await nextTick();

    const enabledButton = getConfirmButton();
    if (!enabledButton) {
      throw new Error('Confirm button not found after update');
    }
    expect((enabledButton.element as HTMLButtonElement).disabled).toBe(false);
  });
});
