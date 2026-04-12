// @vitest-environment happy-dom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type MockFormField = {
  disabled?: boolean;
  label: string;
  name: string;
  readonly?: boolean;
  required?: boolean;
  type: string;
  value?: unknown;
};

type MockFormSession = {
  can_submit: boolean;
  entity_name: string;
  fields: MockFormField[];
  form_session_id: string;
  mode: string;
  record_id?: string;
  remaining_required_fields: string[];
  stage: string;
  submit_policy: string;
};

type MockRuntimeGraphNode = {
  disabled?: boolean;
  id: string;
  kind: string;
  label: string;
  locator: string;
  surfaceId?: string;
};

type MockSnapshotNode = {
  interactable?: boolean;
  kind: string;
  locator: string;
  summary: string;
  surface_id?: string;
};

type LoadRuntimeBridgeOptions = {
  activeSessionId?: null | string;
  activeSessionIdByPageKey?: Record<string, string>;
  activeSurfaceId?: string;
  buildThinPageContextImpl?: (args: {
    locale?: string;
    pageKey: string;
    pageSessionId?: string;
    pageTitle: string;
    snapshot: Record<string, unknown>;
  }) => Record<string, unknown>;
  documentTitle?: string;
  formApis?: Record<string, Record<string, unknown>>;
  html?: string;
  pageSessionId?: null | string;
  resolveRoutePageKeyImpl?: (
    routeLike?: { path?: string },
    explicitPageKey?: string,
  ) => string;
  route?: {
    fullPath: string;
    meta?: Record<string, unknown>;
    name?: string;
  };
  runtimeGraphNodes?: MockRuntimeGraphNode[];
  sessions?: MockFormSession[];
  snapshotNodes?: MockSnapshotNode[];
  surfaceStack?: Array<{
    kind: string;
    surface_id: string;
    title: string;
  }>;
  uiEpoch?: number;
};

function createSession(overrides: Partial<MockFormSession> = {}): MockFormSession {
  return {
    can_submit: true,
    entity_name: 'User',
    fields: [
      {
        label: 'Name',
        name: 'name',
        required: true,
        type: 'text',
        value: 'Alice',
      },
    ],
    form_session_id: 'session-1',
    mode: 'edit',
    remaining_required_fields: [],
    stage: 'editing',
    submit_policy: 'auto',
    ...overrides,
  };
}

async function loadRuntimeBridge(options: LoadRuntimeBridgeOptions = {}) {
  vi.resetModules();

  document.body.innerHTML = options.html ?? '';
  document.title = options.documentTitle ?? 'Runtime Bridge Test';

  const route = options.route ?? {
    fullPath: '/admin/runtime-bridge',
    meta: {
      title: 'Runtime Bridge',
    },
    name: 'runtime-bridge',
  };
  const uiEpoch = options.uiEpoch ?? 7;
  const surfaceStack =
    options.surfaceStack ??
    [
      {
        kind: 'page',
        surface_id: 'surface-page',
        title: 'Runtime Bridge',
      },
    ];
  const activeSurfaceId = options.activeSurfaceId ?? surfaceStack[0]?.surface_id ?? 'surface-page';

  const sessions = new Map(
    (options.sessions ?? []).map((session) => [session.form_session_id, session]),
  );
  const activeSessionIdByPageKey = options.activeSessionIdByPageKey ?? {};
  const formApis = new Map(
    Object.entries(options.formApis ?? {}).map(([sessionId, formApi]) => [sessionId, formApi]),
  );

  const formStateTracker = {
    getActiveSessionByPageKey: vi.fn((pageKey: string) => {
      const sessionId = activeSessionIdByPageKey[pageKey];
      if (!sessionId) {
        return null;
      }
      return sessions.get(sessionId) ?? null;
    }),
    getActiveSession: vi.fn((pageKey?: string) => {
      if (pageKey && activeSessionIdByPageKey[pageKey]) {
        return sessions.get(activeSessionIdByPageKey[pageKey]) ?? null;
      }
      if (!options.activeSessionId) {
        return null;
      }
      return sessions.get(options.activeSessionId) ?? null;
    }),
    getFormApi: vi.fn((sessionId: string) => formApis.get(sessionId) ?? null),
    getSession: vi.fn((sessionId: string) => sessions.get(sessionId) ?? null),
    getSessionId: vi.fn((pageKey: string) => activeSessionIdByPageKey[pageKey] ?? null),
    getTrackedKeys: vi.fn(() => Object.keys(activeSessionIdByPageKey)),
    listSessions: vi.fn(() => [...sessions.values()]),
    setSessionFieldValues: vi.fn((sessionId: string, values: Record<string, unknown>) => {
      const session = sessions.get(sessionId);
      if (!session) {
        return null;
      }
      const updatedSession = {
        ...session,
        fields: session.fields.map((field) =>
          Object.prototype.hasOwnProperty.call(values, field.name)
            ? {
                ...field,
                value: values[field.name],
              }
            : field,
        ),
      };
      sessions.set(sessionId, updatedSession);
      return updatedSession;
    }),
  };

  const runtimeGraphNodes =
    options.runtimeGraphNodes ??
    options.snapshotNodes?.map((node, index) => ({
      disabled: false,
      id: `node-${index + 1}`,
      kind: node.kind,
      label: node.summary,
      locator: node.locator,
      surfaceId: node.surface_id,
    })) ??
    [];

  const runtimeSnapshot = {
    active_surface: {
      id: activeSurfaceId,
    },
    surface_stack: surfaceStack.map((surface) => ({
      id: surface.surface_id,
      kind: surface.kind,
      title: surface.title,
    })),
    ui_epoch: uiEpoch,
    ui_graph: {
      nodes: runtimeGraphNodes,
    },
  };

  const snapshot = {
    active_surface_id: activeSurfaceId,
    interactables_count: options.snapshotNodes?.length ?? 0,
    nodes: options.snapshotNodes ?? [],
    surface_stack: surfaceStack,
    ui_epoch: uiEpoch,
  };

  const resolveRoutePageKey = vi.fn(
    options.resolveRoutePageKeyImpl ??
      ((routeLike?: { path?: string }, explicitPageKey?: string) =>
        explicitPageKey ? `page:${explicitPageKey}` : `route:${routeLike?.path ?? route.fullPath}`),
  );
  const getActivePageSessionId = vi.fn(() => options.pageSessionId ?? null);
  const createUIRuntime = vi.fn(() => ({
    initialize: vi.fn(() => runtimeSnapshot),
    rebuildGraph: vi.fn(() => runtimeSnapshot),
  }));
  const generateSnapshot = vi.fn(() => snapshot);
  const buildThinPageContext = vi.fn(
    options.buildThinPageContextImpl ??
      (({
        locale,
        pageKey,
        pageSessionId,
        pageTitle,
        snapshot: thinSnapshot,
      }: {
        locale?: string;
        pageKey: string;
        pageSessionId?: string;
        pageTitle: string;
        snapshot: Record<string, unknown>;
      }) => ({
        locale,
        page_key: pageKey,
        page_session_id: pageSessionId,
        page_title: pageTitle,
        snapshot: thinSnapshot,
      })),
  );
  const resolveAISecurityPolicy = vi.fn(
    ({
      actionKind,
      element,
    }: {
      actionKind?: string;
      element?: Element | null;
    }) => ({
      canAct:
        element?.getAttribute('data-can-act') !== 'false' &&
        actionKind !== 'blocked-action',
      canRead: element?.getAttribute('data-read') !== 'deny',
      readAccess: element?.getAttribute('data-read') === 'deny' ? 'deny' : 'allow',
      requireConfirm: element?.getAttribute('data-confirm') === 'true',
    }),
  );
  const readValueForAI = vi.fn((value: unknown, decision?: { readAccess?: string }) => {
    if (decision?.readAccess === 'deny') {
      return undefined;
    }
    return String(value ?? '');
  });
  const tAiRuntime = vi.fn(
    (key: string, params?: Record<string, unknown>) =>
      params?.locator ? `${key}:${String(params.locator)}` : key,
  );

  vi.doMock('#/components/business/ai-runtime/page-key-utils', () => ({
    resolveRoutePageKey,
  }));
  vi.doMock('#/composables/use-form-state-tracker', () => ({
    formStateTracker,
  }));
  vi.doMock('#/composables/use-page-session', () => ({
    getActivePageSessionId,
  }));
  vi.doMock('#/locales', () => ({
    $t: vi.fn((key: string) => `locale:${key}`),
  }));
  vi.doMock('#/locales/runtime-locale', () => ({
    resolveRuntimeLocale: () => 'en-US',
  }));
  vi.doMock('../i18n', () => ({
    tAiRuntime,
  }));
  vi.doMock('../security-policy', () => ({
    readValueForAI,
    resolveAISecurityPolicy,
  }));
  vi.doMock('../ui-runtime', () => ({
    createUIRuntime,
  }));
  vi.doMock('../ui-snapshot-generator', () => ({
    UISnapshotGenerator: vi.fn(() => ({
      buildThinPageContext,
      generateSnapshot,
    })),
  }));

  const runtimeBridge = await import('../runtime-bridge');

  return {
    formApis,
    formStateTracker,
    mocks: {
      buildThinPageContext,
      createUIRuntime,
      generateSnapshot,
      getActivePageSessionId,
      readValueForAI,
      resolveAISecurityPolicy,
      resolveRoutePageKey,
      tAiRuntime,
    },
    runtimeBridge,
    sessions,
  };
}

describe('runtime-bridge', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = '';
    document.title = '';
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('initializes the global runtime once and returns thin context, diagnostics, and snapshot data', async () => {
    const { mocks, runtimeBridge } = await loadRuntimeBridge({
      pageSessionId: 'page-session-1',
      route: {
        fullPath: '/admin/ai/runtime',
        meta: {
          title: 'AI Runtime',
        },
        name: 'ai-runtime',
      },
      snapshotNodes: [
        {
          interactable: true,
          kind: 'button',
          locator: 'testid:save',
          summary: 'Save',
          surface_id: 'surface-page',
        },
        {
          interactable: true,
          kind: 'link',
          locator: 'testid:details',
          summary: 'Details',
          surface_id: 'surface-page',
        },
      ],
      uiEpoch: 19,
    });

    const routeGetter = vi.fn(() => ({
      fullPath: '/admin/ai/runtime',
      meta: {
        title: 'AI Runtime',
      },
      name: 'ai-runtime',
    }));

    const firstRuntime = runtimeBridge.ensureGlobalUIRuntime({
      getRoute: routeGetter,
    });
    const secondRuntime = runtimeBridge.ensureGlobalUIRuntime();

    expect(firstRuntime).toBe(secondRuntime);
    expect(mocks.createUIRuntime).toHaveBeenCalledTimes(1);

    const pageContext = runtimeBridge.getRuntimeThinPageContext('explicit-page');
    expect(pageContext).toMatchObject({
      locale: 'en-US',
      page_key: 'page:explicit-page',
      page_session_id: 'page-session-1',
      page_title: 'locale:AI Runtime',
    });

    const diagnostics = runtimeBridge.getRuntimePageContextDiagnostics();
    expect(diagnostics).toMatchObject({
      interactables_count: 2,
      source: 'ui_runtime',
      ui_epoch: 19,
    });
    expect(diagnostics.size_bytes).toBeGreaterThan(0);

    expect(runtimeBridge.getRuntimeSnapshot()).toEqual({
      active_surface_id: 'surface-page',
      interactables_count: 2,
      nodes: [
        {
          interactable: true,
          kind: 'button',
          locator: 'testid:save',
          summary: 'Save',
          surface_id: 'surface-page',
        },
        {
          interactable: true,
          kind: 'link',
          locator: 'testid:details',
          summary: 'Details',
          surface_id: 'surface-page',
        },
      ],
      surface_stack: [
        {
          kind: 'page',
          surface_id: 'surface-page',
          title: 'Runtime Bridge',
        },
      ],
      ui_epoch: 19,
    });
  });

  it('returns null when thin page context has an empty page_key', async () => {
    const { runtimeBridge } = await loadRuntimeBridge({
      buildThinPageContextImpl: () => ({
        page_key: '',
      }),
      resolveRoutePageKeyImpl: () => '',
      route: {
        fullPath: '/admin/empty-page-key',
        meta: {},
        name: 'empty-page-key',
      },
    });

    expect(runtimeBridge.getRuntimeThinPageContext()).toBeNull();
  });

  it('falls back to document.title and then pageKey when route title is unavailable', async () => {
    const first = await loadRuntimeBridge({
      documentTitle: 'Document Fallback Title',
      route: {
        fullPath: '/admin/title-fallback-doc',
        meta: {
          title: '   ',
        },
        name: 'title-fallback-doc',
      },
    });

    expect(first.runtimeBridge.getRuntimeThinPageContext()).toMatchObject({
      page_key: 'page:/',
      page_title: 'Document Fallback Title',
    });

    const second = await loadRuntimeBridge({
      documentTitle: '',
      route: {
        fullPath: '/admin/title-fallback-page-key',
        meta: {},
        name: 'title-fallback-page-key',
      },
    });

    expect(second.runtimeBridge.getRuntimeThinPageContext()).toMatchObject({
      page_key: 'page:/',
      page_title: 'page:/',
    });
  });

  it('localizes route title keys and includes runtime locale in thin page context', async () => {
    const loaded = await loadRuntimeBridge({
      route: {
        fullPath: '/admin/dashboard',
        meta: {
          title: 'page.dashboard.title',
        },
        name: 'dashboard',
      },
    });

    expect(loaded.runtimeBridge.getRuntimeThinPageContext()).toMatchObject({
      locale: 'en-US',
    });
  });

  it('reads runtime regions from visible DOM content', async () => {
    const { runtimeBridge } = await loadRuntimeBridge({
      html: `
        <div class="ant-modal">
          <section data-testid="profile-region">
            <h2>Profile</h2>
            <label>Name</label>
            <span>Alice</span>
            <div>
              <label data-label="Role"></label>
              <span>Admin</span>
            </div>
          </section>
        </div>
      `,
      surfaceStack: [
        {
          kind: 'page',
          surface_id: 'surface-page',
          title: 'Runtime Bridge',
        },
        {
          kind: 'modal',
          surface_id: 'surface-modal',
          title: 'Profile Modal',
        },
      ],
    });

    const result = runtimeBridge.readRuntimeRegion('testid:profile-region');

    expect(result).toMatchObject({
      items: [
        {
          label: 'Name',
          value: 'Alice',
        },
        {
          label: 'Role',
          value: 'Admin',
        },
      ],
      region_locator: 'testid:profile-region',
      surface_id: 'surface-modal',
      text: expect.stringContaining('Alice'),
      title: 'Profile',
      truncated: false,
    });
  });

  it('reads form-like region text and uses surface fallback when no title exists', async () => {
    const { runtimeBridge } = await loadRuntimeBridge({
      html: `
        <div data-testid="plain-region">
          <input name="email" value="alice@example.com" />
        </div>
      `,
      surfaceStack: [
        {
          kind: 'page',
          surface_id: 'surface-page-fallback',
          title: 'Runtime Bridge',
        },
      ],
    });

    const result = runtimeBridge.readRuntimeRegion('name:email');

    expect(result).toMatchObject({
      items: [],
      region_locator: 'name:email',
      surface_id: 'surface-page-fallback',
      text: 'alice@example.com',
      truncated: false,
    });
    expect(result.title).toBeUndefined();
  });

  it('throws when the runtime region locator cannot be found', async () => {
    const { runtimeBridge } = await loadRuntimeBridge();

    expect(() => runtimeBridge.readRuntimeRegion('testid:missing')).toThrow(
      'regionLocatorNotFound:testid:missing',
    );
  });

  it('reads runtime tables with pagination metadata', async () => {
    const { runtimeBridge } = await loadRuntimeBridge({
      html: `
        <div data-testid="user-table">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>Alice</td><td>Admin</td></tr>
              <tr><td>Bob</td><td>Editor</td></tr>
              <tr><td>Carol</td><td>Owner</td></tr>
            </tbody>
          </table>
        </div>
      `,
    });

    expect(
      runtimeBridge.readRuntimeTable({
        locator: 'testid:user-table',
        page: 2,
        pageSize: 2,
      }),
    ).toEqual({
      columns: ['Name', 'Role'],
      has_more: false,
      page: 2,
      page_size: 2,
      rows: [
        {
          Name: 'Carol',
          Role: 'Owner',
        },
      ],
      surface_id: 'surface-page',
      table_locator: 'testid:user-table',
      total_rows: 3,
      truncated: false,
    });
  });

  it('derives table headers from first tbody row and clamps page/pageSize bounds', async () => {
    const { runtimeBridge } = await loadRuntimeBridge({
      html: `
        <div data-testid="table-no-thead">
          <table>
            <tbody>
              <tr><td>Name</td><td>Role</td></tr>
              <tr><td>Alice</td><td>Admin</td></tr>
              <tr><td>Bob</td><td>Editor</td></tr>
            </tbody>
          </table>
        </div>
      `,
    });

    expect(
      runtimeBridge.readRuntimeTable({
        locator: 'testid:table-no-thead',
        page: 0,
        pageSize: 999,
      }),
    ).toEqual({
      columns: ['Name', 'Role'],
      has_more: false,
      page: 1,
      page_size: 100,
      rows: [
        {
          Name: 'Name',
          Role: 'Role',
        },
        {
          Name: 'Alice',
          Role: 'Admin',
        },
        {
          Name: 'Bob',
          Role: 'Editor',
        },
      ],
      surface_id: 'surface-page',
      table_locator: 'testid:table-no-thead',
      total_rows: 3,
      truncated: false,
    });
  });

  it('throws when the table locator does not resolve to a table', async () => {
    const { runtimeBridge } = await loadRuntimeBridge({
      html: `
        <div data-testid="not-a-table">
          <div>Not a table</div>
        </div>
      `,
    });

    expect(() =>
      runtimeBridge.readRuntimeTable({
        locator: 'testid:not-a-table',
      }),
    ).toThrow('tableLocatorNotFound:testid:not-a-table');
  });

  it('lists interactables by surface and exposes safety metadata', async () => {
    const { runtimeBridge } = await loadRuntimeBridge({
      html: `
        <button data-testid="save-btn" data-confirm="true">Save</button>
        <input data-testid="name-input" data-can-act="false" value="Alice" />
        <a data-testid="settings-link" href="/settings">Settings</a>
        <div data-testid="ignored-text">Ignored</div>
      `,
      snapshotNodes: [
        {
          interactable: true,
          kind: 'button',
          locator: 'testid:save-btn',
          summary: 'Save',
          surface_id: 'surface-modal',
        },
        {
          interactable: false,
          kind: 'input',
          locator: 'testid:name-input',
          summary: 'Name',
          surface_id: 'surface-modal',
        },
        {
          interactable: false,
          kind: 'text',
          locator: 'testid:ignored-text',
          summary: 'Ignored',
          surface_id: 'surface-page',
        },
        {
          interactable: true,
          kind: 'link',
          locator: 'testid:settings-link',
          summary: 'Settings',
          surface_id: 'surface-page',
        },
      ],
      surfaceStack: [
        {
          kind: 'page',
          surface_id: 'surface-page',
          title: 'Runtime Bridge',
        },
        {
          kind: 'modal',
          surface_id: 'surface-modal',
          title: 'Editor',
        },
      ],
    });

    expect(runtimeBridge.listRuntimeInteractables('surface-modal')).toEqual({
      count: 2,
      items: [
        {
          enabled: true,
          kind: 'button',
          label: 'Save',
          locator: 'testid:save-btn',
          requires_confirmation: true,
          surface_id: 'surface-modal',
        },
        {
          enabled: false,
          kind: 'input',
          label: 'Name',
          locator: 'testid:name-input',
          requires_confirmation: false,
          surface_id: 'surface-modal',
        },
      ],
      surface_id: 'surface-modal',
      truncated: true,
    });
  });

  it('lists interactables across surfaces when surfaceId is omitted', async () => {
    const { runtimeBridge } = await loadRuntimeBridge({
      html: `
        <button data-testid="save-btn">Save</button>
        <a data-testid="settings-link" href="/settings">Settings</a>
      `,
      snapshotNodes: [
        {
          interactable: true,
          kind: 'button',
          locator: 'testid:save-btn',
          summary: 'Save',
          surface_id: 'surface-modal',
        },
        {
          interactable: true,
          kind: 'link',
          locator: 'testid:settings-link',
          summary: 'Settings',
          surface_id: 'surface-page',
        },
      ],
    });

    expect(runtimeBridge.listRuntimeInteractables()).toEqual({
      count: 2,
      items: [
        {
          enabled: true,
          kind: 'button',
          label: 'Save',
          locator: 'testid:save-btn',
          requires_confirmation: false,
          surface_id: 'surface-modal',
        },
        {
          enabled: true,
          kind: 'link',
          label: 'Settings',
          locator: 'testid:settings-link',
          requires_confirmation: false,
          surface_id: 'surface-page',
        },
      ],
      surface_id: undefined,
      truncated: false,
    });
  });

  it('lists page interactables when filtering by page surface id', async () => {
    const { runtimeBridge } = await loadRuntimeBridge({
      html: `
        <button data-testid="save-btn">Save</button>
        <a data-testid="settings-link" href="/settings">Settings</a>
      `,
      snapshotNodes: [
        {
          interactable: true,
          kind: 'button',
          locator: 'testid:save-btn',
          summary: 'Save',
          surface_id: 'surface-modal',
        },
        {
          interactable: true,
          kind: 'link',
          locator: 'testid:settings-link',
          summary: 'Settings',
          surface_id: 'surface-page',
        },
      ],
      surfaceStack: [
        {
          kind: 'page',
          surface_id: 'surface-page',
          title: 'Runtime Bridge',
        },
        {
          kind: 'modal',
          surface_id: 'surface-modal',
          title: 'Editor',
        },
      ],
    });

    expect(runtimeBridge.listRuntimeInteractables('surface-page')).toEqual({
      count: 1,
      items: [
        {
          enabled: true,
          kind: 'link',
          label: 'Settings',
          locator: 'testid:settings-link',
          requires_confirmation: false,
          surface_id: 'surface-page',
        },
      ],
      surface_id: 'surface-page',
      truncated: true,
    });
  });

  it('returns a missing-session error when no runtime form session is active', async () => {
    const { runtimeBridge } = await loadRuntimeBridge();

    await expect(runtimeBridge.getRuntimeFormState()).resolves.toMatchObject({
      error_type: 'form_session_not_found',
      success: false,
    });
  });

  it('returns runtime form state for the active session', async () => {
    const session = createSession({
      fields: [
        {
          label: 'Name',
          name: 'name',
          required: true,
          type: 'text',
          value: 'Alice',
        },
        {
          label: 'Role',
          name: 'role',
          readonly: true,
          type: 'text',
          value: 'Admin',
        },
      ],
      remaining_required_fields: ['name'],
    });
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      html: `
        <input name="name" value="Alice" />
        <input name="role" value="Admin" />
      `,
      sessions: [session],
    });

    await expect(runtimeBridge.getRuntimeFormState()).resolves.toMatchObject({
      data: {
        entity_name: 'User',
        fields: [
          expect.objectContaining({
            label: 'Name',
            name: 'name',
            value: 'Alice',
          }),
          expect.objectContaining({
            label: 'Role',
            name: 'role',
            readonly: true,
            value: 'Admin',
          }),
        ],
        remaining_required_fields: ['name'],
      },
      success: true,
    });
  });

  it('resolves the active runtime form session by current pageKey', async () => {
    const session = createSession({
      form_session_id: 'session-by-page-key',
    });
    const pageKey = 'page:/';
    const { formStateTracker, runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: null,
      activeSessionIdByPageKey: {
        [pageKey]: session.form_session_id,
      },
      route: {
        fullPath: '/admin/runtime-form-by-page',
        meta: {},
        name: 'runtime-form-by-page',
      },
      sessions: [session],
    });

    await expect(runtimeBridge.getRuntimeFormState()).resolves.toMatchObject({
      data: {
        form_session_id: 'session-by-page-key',
      },
      success: true,
    });
    expect(formStateTracker.getActiveSessionByPageKey).toHaveBeenCalledWith(
      pageKey,
    );
  });

  it('updates a writable runtime form field', async () => {
    const session = createSession();
    const setValues = vi.fn();
    const getValues = vi.fn(async () => ({
      name: 'Bob',
    }));
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      formApis: {
        [session.form_session_id]: {
          getValues,
          setValues,
        },
      },
      html: `
        <input name="name" value="Alice" />
      `,
      sessions: [session],
    });

    await expect(
      runtimeBridge.setRuntimeFormField({
        fieldName: 'name',
        value: 'Bob',
      }),
    ).resolves.toMatchObject({
      data: {
        fields_updated: ['name'],
        form_session: {
          fields: [
            expect.objectContaining({
              name: 'name',
              value: 'Bob',
            }),
          ],
        },
      },
      success: true,
    });
    expect(setValues).toHaveBeenCalledWith({
      name: 'Bob',
    });
  });

  it('reads and updates form state using explicit formSessionId', async () => {
    const targetSession = createSession({
      fields: [
        {
          label: 'Name',
          name: 'name',
          type: 'text',
          value: 'Alice',
        },
      ],
      form_session_id: 'session-target',
    });
    const otherSession = createSession({
      fields: [
        {
          label: 'Name',
          name: 'name',
          type: 'text',
          value: 'Other',
        },
      ],
      form_session_id: 'session-other',
    });
    const setValues = vi.fn();
    const getValues = vi.fn(async () => ({
      name: 'FromExplicitSession',
    }));
    const { runtimeBridge } = await loadRuntimeBridge({
      formApis: {
        [targetSession.form_session_id]: {
          getValues,
          setValues,
        },
      },
      html: `
        <input name="name" value="Alice" />
      `,
      sessions: [targetSession, otherSession],
    });

    await expect(
      runtimeBridge.getRuntimeFormState(targetSession.form_session_id),
    ).resolves.toMatchObject({
      data: {
        form_session_id: 'session-target',
      },
      success: true,
    });

    await expect(
      runtimeBridge.setRuntimeFormField({
        fieldName: 'name',
        formSessionId: targetSession.form_session_id,
        value: 'FromExplicitSession',
      }),
    ).resolves.toMatchObject({
      data: {
        fields_updated: ['name'],
      },
      success: true,
    });

    await expect(
      runtimeBridge.fillRuntimeForm({
        fields: {
          name: 'FromExplicitSession',
        },
        formSessionId: targetSession.form_session_id,
      }),
    ).resolves.toMatchObject({
      data: {
        fields_updated: ['name'],
      },
      success: true,
    });

    expect(setValues).toHaveBeenCalledTimes(2);
    expect(setValues).toHaveBeenNthCalledWith(1, {
      name: 'FromExplicitSession',
    });
    expect(setValues).toHaveBeenNthCalledWith(2, {
      name: 'FromExplicitSession',
    });
  });

  it('returns form_api_unavailable when applying updates without form api', async () => {
    const session = createSession();
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      sessions: [session],
    });

    await expect(
      runtimeBridge.setRuntimeFormField({
        fieldName: 'name',
        value: 'Bob',
      }),
    ).resolves.toMatchObject({
      error_type: 'form_api_unavailable',
      success: false,
    });
  });

  it('keeps writable updates when formApi.getValues throws during fill/set', async () => {
    const session = createSession();
    const setValues = vi.fn();
    const getValues = vi.fn(async () => {
      throw new Error('form is stabilizing');
    });
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      formApis: {
        [session.form_session_id]: {
          getValues,
          setValues,
        },
      },
      html: `
        <input name="name" value="Alice" />
      `,
      sessions: [session],
    });

    await expect(
      runtimeBridge.fillRuntimeForm({
        fields: {
          name: 'FallbackValue',
        },
      }),
    ).resolves.toMatchObject({
      data: {
        fields_updated: ['name'],
        form_session: {
          fields: [
            expect.objectContaining({
              name: 'name',
              value: 'FallbackValue',
            }),
          ],
        },
      },
      success: true,
    });
  });

  it('fills runtime form fields and reports readonly or missing fields separately', async () => {
    const session = createSession({
      fields: [
        {
          label: 'Name',
          name: 'name',
          type: 'text',
          value: 'Alice',
        },
        {
          label: 'Status',
          name: 'status',
          readonly: true,
          type: 'text',
          value: 'Locked',
        },
      ],
    });
    const setValues = vi.fn();
    const getValues = vi.fn(async () => ({
      name: 'Bob',
      status: 'Locked',
    }));
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      formApis: {
        [session.form_session_id]: {
          getValues,
          setValues,
        },
      },
      html: `
        <input name="name" value="Alice" />
        <input name="status" value="Locked" />
      `,
      sessions: [session],
    });

    await expect(
      runtimeBridge.fillRuntimeForm({
        fields: {
          missing: 'x',
          name: 'Bob',
          status: 'Active',
        },
      }),
    ).resolves.toMatchObject({
      data: {
        fields_failed: [
          {
            error: 'field_not_found',
            field: 'missing',
          },
          {
            error: 'field_not_writable',
            field: 'status',
          },
        ],
        fields_updated: ['name'],
      },
      success: true,
    });
    expect(setValues).toHaveBeenCalledWith({
      name: 'Bob',
    });
  });

  it('fails to fill runtime form fields when none of them are writable', async () => {
    const session = createSession({
      fields: [
        {
          label: 'Status',
          name: 'status',
          readonly: true,
          type: 'text',
          value: 'Locked',
        },
      ],
    });
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      formApis: {
        [session.form_session_id]: {
          getValues: vi.fn(async () => ({
            status: 'Locked',
          })),
          setValues: vi.fn(),
        },
      },
      html: `
        <input name="status" value="Locked" />
      `,
      sessions: [session],
    });

    await expect(
      runtimeBridge.fillRuntimeForm({
        fields: {
          missing: 'x',
          status: 'Active',
        },
      }),
    ).resolves.toMatchObject({
      error_type: 'no_writable_fields',
      success: false,
    });
  });

  it('returns a missing-session error when submitting a runtime form without an active session', async () => {
    const { runtimeBridge } = await loadRuntimeBridge();

    await expect(runtimeBridge.submitRuntimeForm({})).resolves.toMatchObject({
      error_type: 'form_session_not_found',
      success: false,
    });
  });

  it('requires confirmation before submitting confirm-policy forms', async () => {
    const session = createSession({
      submit_policy: 'confirm',
    });
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      formApis: {
        [session.form_session_id]: {
          getValues: vi.fn(async () => ({
            name: 'Alice',
          })),
          submitForm: vi.fn(),
        },
      },
      html: `
        <input name="name" value="Alice" />
      `,
      sessions: [session],
    });

    await expect(runtimeBridge.submitRuntimeForm({})).resolves.toMatchObject({
      data: {
        form_session: expect.objectContaining({
          form_session_id: session.form_session_id,
        }),
      },
      error_type: 'confirmation_required',
      success: false,
    });
  });

  it('returns an explicit error when the runtime form API cannot submit', async () => {
    const session = createSession();
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      formApis: {
        [session.form_session_id]: {
          getValues: vi.fn(async () => ({
            name: 'Alice',
          })),
        },
      },
      sessions: [session],
    });

    await expect(runtimeBridge.submitRuntimeForm({})).resolves.toMatchObject({
      error_type: 'form_submit_unavailable',
      success: false,
    });
  });

  it('submits the runtime form and refreshes the tracked session state', async () => {
    const session = createSession();
    const submitForm = vi.fn(async () => undefined);
    const getValues = vi.fn(async () => ({
      name: 'Carol',
    }));
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      formApis: {
        [session.form_session_id]: {
          getValues,
          submitForm,
        },
      },
      html: `
        <input name="name" value="Alice" />
      `,
      sessions: [session],
    });

    await expect(
      runtimeBridge.submitRuntimeForm({
        confirm: true,
      }),
    ).resolves.toMatchObject({
      data: {
        form_session: {
          fields: [
            expect.objectContaining({
              name: 'name',
              value: 'Carol',
            }),
          ],
        },
      },
      success: true,
    });
    expect(submitForm).toHaveBeenCalledTimes(1);
  });

  it('submits form successfully when submit getValues throws after submit', async () => {
    const session = createSession({
      fields: [
        {
          label: 'Name',
          name: 'name',
          type: 'text',
          value: 'Alice',
        },
      ],
    });
    const submitForm = vi.fn(async () => undefined);
    const getValues = vi.fn(async () => {
      throw new Error('form closed');
    });
    const { runtimeBridge } = await loadRuntimeBridge({
      activeSessionId: session.form_session_id,
      formApis: {
        [session.form_session_id]: {
          getValues,
          submitForm,
        },
      },
      html: `
        <input name="name" value="Alice" />
      `,
      sessions: [session],
    });

    await expect(runtimeBridge.submitRuntimeForm({})).resolves.toMatchObject({
      data: {
        form_session: {
          fields: [
            expect.objectContaining({
              name: 'name',
              value: 'Alice',
            }),
          ],
          form_session_id: session.form_session_id,
        },
      },
      success: true,
    });
    expect(submitForm).toHaveBeenCalledTimes(1);
  });
});
