import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import PluginInstallWizard from '../modules/PluginInstallWizard.vue';

interface MarketplacePluginTarget {
  display_name: string;
  name: string;
  slug: string;
  version: string;
}

interface PluginInstallWizardVm {
  open: () => unknown;
  openMarketplace: (target: MarketplacePluginTarget) => Promise<unknown>;
}

const mockRefs = vi.hoisted(() => ({
  installPluginApi: vi.fn(),
  marketplaceConfirmInstallApi: vi.fn(),
  marketplacePreviewInstallApi: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  previewPluginInstallApi: vi.fn(),
}));

vi.mock('#/api/admin/plugin', () => ({
  getPluginTenantExposureColor: (mode: string) => `color:${mode}`,
  getPluginTenantExposureLabelKey: (mode: string) =>
    mode === 'specified_tenants'
      ? 'admin.plugin.compatibility.tenantExposure.specifiedTenants'
      : `admin.plugin.compatibility.tenantExposure.${mode}`,
  installPluginApi: mockRefs.installPluginApi,
  previewPluginInstallApi: mockRefs.previewPluginInstallApi,
  resolvePluginCompatibilityProfile: (source: {
    compatibility_profile?: {
      editions?: string[];
      saas_compatible?: boolean;
      single_management_compatible?: boolean;
      tenant_exposure?: {
        mode?: string;
        requires_explicit_assignment?: boolean;
      };
    };
  }) => {
    const profile = source.compatibility_profile ?? {};
    const tenantExposure = profile.tenant_exposure ?? {};
    return {
      editions: profile.editions ?? ['saas'],
      saasCompatible: profile.saas_compatible ?? true,
      singleManagementCompatible:
        profile.single_management_compatible ??
        (profile.editions ?? []).includes('single-management'),
      surfaces: [],
      tenantAssignmentRequired:
        tenantExposure.requires_explicit_assignment === true,
      tenantExposureMode: tenantExposure.mode ?? 'scope_inherited',
    };
  },
}));

vi.mock('#/api/admin/plugin-marketplace', () => ({
  marketplaceConfirmInstallApi: mockRefs.marketplaceConfirmInstallApi,
  marketplacePreviewInstallApi: mockRefs.marketplacePreviewInstallApi,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/plugin-metadata-icon', () => ({
  resolvePluginMetadataIcon: () => ({
    kind: 'icon',
    icon: 'lucide:puzzle',
  }),
}));

vi.mock('#/utils/scope-helpers', () => ({
  getScopeColor: () => 'blue',
  getScopeText: (scope: string) => `scope:${scope}`,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIcon',
    setup() {
      return () => h('i');
    },
  }),
}));

vi.mock('ant-design-vue', () => {
  const ModalStub = defineComponent({
    name: 'AModal',
    props: {
      open: {
        type: Boolean,
        default: false,
      },
    },
    setup(props, { slots }) {
      return () => (props.open ? h('div', slots.default?.()) : null);
    },
  });

  const ButtonStub = defineComponent({
    name: 'AButton',
    props: {
      disabled: {
        type: Boolean,
        default: false,
      },
      loading: {
        type: Boolean,
        default: false,
      },
    },
    emits: ['click'],
    setup(props, { emit, slots }) {
      return () =>
        h(
          'button',
          {
            disabled: props.disabled,
            'data-loading': String(props.loading),
            onClick: () => emit('click'),
          },
          slots.default?.(),
        );
    },
  });

  const AlertStub = defineComponent({
    name: 'AAlert',
    props: {
      description: {
        type: String,
        default: '',
      },
      message: {
        type: String,
        default: '',
      },
    },
    setup(props) {
      return () => h('div', `${props.message}${props.description}`);
    },
  });

  const TagStub = defineComponent({
    name: 'ATag',
    setup(_props, { slots }) {
      return () => h('span', slots.default?.());
    },
  });

  const UploadDraggerStub = defineComponent({
    name: 'AUploadDragger',
    props: {
      beforeUpload: {
        type: Function,
        required: false,
      },
      disabled: {
        type: Boolean,
        default: false,
      },
    },
    setup(props, { slots }) {
      return () =>
        h(
          'button',
          {
            disabled: props.disabled,
            'data-testid': 'upload-dragger',
            onClick: () =>
              props.beforeUpload?.(
                new File([new Uint8Array([1])], 'demo-plugin.zip', {
                  type: 'application/zip',
                }),
              ),
          },
          slots.default?.(),
        );
    },
  });

  return {
    Alert: AlertStub,
    Button: ButtonStub,
    Modal: ModalStub,
    Tag: TagStub,
    Upload: {
      Dragger: UploadDraggerStub,
    },
    message: {
      error: mockRefs.messageError,
      success: mockRefs.messageSuccess,
    },
  };
});

function buildPreviewResponse() {
  return {
    plugin_info: {
      name: 'weather-widget',
      display_name: 'Weather Widget',
      version: '1.2.3',
      scope: 'admin_only',
      author: 'NovusAI',
      description: 'Shows live weather.',
    },
    install_manifest: {
      frontend_pages: 1,
      frontend_pages_details: ['Weather Dashboard'],
    },
    dependencies: {
      plugins: [
        {
          enabled: false,
          installed: false,
          installed_version: null,
          message: 'Plugin dependency dep-plugin is not installed',
          plugin: 'dep-plugin',
          source: 'dependencies.plugins',
          state: 'missing',
          version: '*',
        },
      ],
      python: [
        {
          installed: false,
          installed_version: null,
          message:
            'Python dependency preview-missing-demo-package is missing or has a version mismatch',
          package: 'preview-missing-demo-package',
          requirement: 'preview-missing-demo-package>=1.0',
          satisfied: false,
          state: 'missing',
        },
      ],
    },
    conflicts: [],
    capabilities: [],
    compatibility: {},
    compatibility_profile: {
      editions: ['saas', 'single-management'],
      saas_compatible: true,
      single_management_compatible: true,
      tenant_exposure: {
        mode: 'specified_tenants',
        requires_explicit_assignment: true,
      },
    },
    warnings: [],
    preview_token: 'preview-token',
  };
}

describe('pluginInstallWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRefs.marketplaceConfirmInstallApi.mockResolvedValue({});
    mockRefs.installPluginApi.mockResolvedValue({});
    mockRefs.marketplacePreviewInstallApi.mockResolvedValue(
      buildPreviewResponse(),
    );
    mockRefs.previewPluginInstallApi.mockResolvedValue(buildPreviewResponse());
  });

  it('uses preview token for marketplace install confirmations', async () => {
    const wrapper = mount(PluginInstallWizard);
    const vm = wrapper.vm as unknown as PluginInstallWizardVm;

    await vm.openMarketplace({
      slug: 'weather-widget',
      name: 'weather-widget',
      display_name: 'Weather Widget',
      version: '1.2.3',
    });
    await flushPromises();

    expect(mockRefs.marketplacePreviewInstallApi).toHaveBeenCalledWith(
      'weather-widget',
    );
    expect(wrapper.text()).toContain('Weather Widget');
    expect(wrapper.text()).toContain('admin.plugin.preview.pythonDeps');
    expect(wrapper.text()).toContain('admin.plugin.preview.pluginDeps');
    expect(wrapper.text()).not.toContain('Python deps');
    expect(wrapper.text()).not.toContain('plugin deps');

    const confirmButton = wrapper
      .findAll('button')
      .find((button) =>
        button.text().includes('admin.plugin.preview.confirmInstall'),
      );

    expect(confirmButton).toBeTruthy();
    if (!confirmButton) {
      throw new Error('Expected confirm install button to exist');
    }
    await confirmButton.trigger('click');
    await flushPromises();

    expect(mockRefs.marketplaceConfirmInstallApi).toHaveBeenCalledWith(
      'weather-widget',
      {
        previewToken: 'preview-token',
      },
    );
    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'admin.plugin.messages.installSuccess',
    );
    expect(wrapper.emitted('installed')).toHaveLength(1);
  });

  it('uses preview token for uploaded plugin installations', async () => {
    const wrapper = mount(PluginInstallWizard);
    const vm = wrapper.vm as unknown as PluginInstallWizardVm;

    vm.open();
    await flushPromises();

    const uploadButton = wrapper.find('[data-testid="upload-dragger"]');
    await uploadButton.trigger('click');
    await flushPromises();

    expect(mockRefs.previewPluginInstallApi).toHaveBeenCalledTimes(1);

    const confirmButton = wrapper
      .findAll('button')
      .find((button) =>
        button.text().includes('admin.plugin.preview.confirmInstall'),
      );

    expect(confirmButton).toBeTruthy();
    if (!confirmButton) {
      throw new Error('Expected confirm install button to exist');
    }
    await confirmButton.trigger('click');
    await flushPromises();

    expect(mockRefs.installPluginApi).toHaveBeenCalledTimes(1);
    expect(mockRefs.installPluginApi.mock.calls[0]?.[1]).toBe('preview-token');
  });

  it('fail-closes confirmation when preview reports conflicts', async () => {
    mockRefs.marketplacePreviewInstallApi.mockResolvedValue({
      ...buildPreviewResponse(),
      conflicts: [
        {
          reason:
            "Adapter 'weather-widget' is already registered by plugin 'installed-plugin'",
        },
      ],
      warnings: ['Localized warning from backend'],
    });

    const wrapper = mount(PluginInstallWizard);
    const vm = wrapper.vm as unknown as PluginInstallWizardVm;

    await vm.openMarketplace({
      slug: 'weather-widget',
      name: 'weather-widget',
      display_name: 'Weather Widget',
      version: '1.2.3',
    });
    await flushPromises();

    expect(wrapper.text()).toContain('Localized warning from backend');
    expect(wrapper.text()).toContain(
      "Adapter 'weather-widget' is already registered by plugin 'installed-plugin'",
    );

    const confirmButton = wrapper
      .findAll('button')
      .find((button) =>
        button.text().includes('admin.plugin.preview.confirmInstall'),
      );

    expect(confirmButton).toBeTruthy();
    if (!confirmButton) {
      throw new Error('Expected confirm install button to exist');
    }
    expect(confirmButton.attributes('disabled')).toBeDefined();
  });

  it('[structural] renders compatibility tags from install preview profile', async () => {
    const wrapper = mount(PluginInstallWizard);
    const vm = wrapper.vm as unknown as PluginInstallWizardVm;

    await vm.openMarketplace({
      slug: 'weather-widget',
      name: 'weather-widget',
      display_name: 'Weather Widget',
      version: '1.2.3',
    });
    await flushPromises();

    expect(wrapper.text()).toContain(
      'admin.plugin.compatibility.edition.saasCompatible',
    );
    expect(wrapper.text()).toContain(
      'admin.plugin.compatibility.edition.singleManagementCompatible',
    );
    expect(wrapper.text()).toContain(
      'admin.plugin.compatibility.tenantExposure.specifiedTenants',
    );
    expect(wrapper.text()).toContain(
      'admin.plugin.compatibility.tenantExposure.explicitRequired',
    );
  });
});
