/**
 * Declarative CRUD list composable — renderless data layer
 * 声明式 CRUD 列表 Composable — 无渲染数据层
 *
 * Provides full list data management (loading, search, pagination, CRUD, recycle bin)
 * without binding to any rendering component (VxeTable / Card / etc.).
 * Pages can freely choose rendering (card grid, config panel, Master-Detail, etc.).
 * 提供完整的列表数据管理能力，不绑定渲染组件。
 *
 * @example Card grid / 卡片网格
 * ```ts
 * const {
 *   list, total, loading, currentPage,
 *   FormDrawer, onCreate, onEdit, onDelete,
 *   onSearch, onPageChange,
 * } = useCrudList<KBItem>({
 *   api: { list: getListApi, resource: '/admin/ai/knowledge-bases' },
 *   formComponent: KBForm,
 *   i18nPrefix: 'admin.knowledgeBase',
 *   pageSize: 12,
 *   createPermission: 'ai_knowledge_base:create',
 * });
 * ```
 *
 * @example Master-Detail (with selectable) / Master-Detail（配合 selectable）
 * ```ts
 * const {
 *   list, selectedId, selectedItem, onSelect,
 * } = useCrudList<PackageInfo>({
 *   api: { list: getPackageListApi, resource: '/admin/ai/skill-packages' },
 *   i18nPrefix: 'admin.ai.skillPackage',
 *   selectable: true,
 *   defaultSelect: 'first',
 *   clientFilter: (item, kw) => item.name.toLowerCase().includes(kw),
 * });
 * ```
 */

import type { Component, ComputedRef, Ref } from 'vue';

import {
  computed,
  h,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  ref,
} from 'vue';

import { useVbenDrawer, useVbenModal } from '@vben/common-ui';

import { message, Modal } from 'ant-design-vue';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

// ============================================================
// Dependency block types & imperative modal
// 依赖阻止类型 & 命令式弹窗
// ============================================================

interface DependencyItem {
  id: number;
  label?: string;
}

interface DependencyGroup {
  type: string;
  count: number;
  items: DependencyItem[];
}

const DEP_MAX_PREVIEW = 5;

/** Imperatively show dependency block modal (no component ref needed) / 命令式显示依赖阻止弹窗 */
function showDependencyBlock(deps: DependencyGroup[], name: string) {
  const title = name
    ? `${$t('common.dependency.title')}「${name}」`
    : $t('common.dependency.title');

  Modal.warning({
    title,
    width: 520,
    centered: true,
    content: () =>
      h('div', {}, [
        h(
          'div',
          {
            class:
              'mb-3 rounded-lg bg-warning/10 px-4 py-3 text-sm text-foreground',
          },
          $t('common.dependency.blocked'),
        ),
        ...deps.map((dep) =>
          h(
            'div',
            {
              key: dep.type,
              class:
                'mb-2 rounded-lg border border-border/50 bg-accent/5 px-4 py-3',
            },
            [
              h(
                'div',
                {
                  class:
                    'mb-1 flex items-center justify-between text-sm font-medium',
                },
                [
                  h('span', {}, $t(`common.dependency.model.${dep.type}`)),
                  h('span', { class: 'text-xs text-warning' }, `${dep.count}`),
                ],
              ),
              ...(dep.items || []).slice(0, DEP_MAX_PREVIEW).map((item) =>
                h(
                  'div',
                  {
                    key: item.id,
                    class: 'pl-2 text-xs text-muted-foreground',
                  },
                  `• ${item.label || `#${item.id}`}`,
                ),
              ),
              dep.count > DEP_MAX_PREVIEW
                ? h(
                    'div',
                    { class: 'pl-2 text-xs italic text-muted-foreground/60' },
                    $t('common.dependency.moreItems', {
                      count: dep.count - DEP_MAX_PREVIEW,
                    }),
                  )
                : null,
            ],
          ),
        ),
        h(
          'div',
          {
            class:
              'mt-3 rounded-lg bg-primary/5 px-4 py-2.5 text-xs text-muted-foreground',
          },
          $t('common.dependency.description'),
        ),
      ]),
  });
}

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Toggle status API type / 切换状态 API 类型 */
export type ToggleStatusApi = (
  id: number | string,
  data: Record<string, unknown>,
) => Promise<unknown>;

/** Toggle status config / 切换状态配置 */
export type ToggleStatusConfig = Record<string, ToggleStatusApi>;

/** API config / API 配置 */
export interface CrudListApiConfig<T = unknown> {
  /** List query API (required) / 列表查询 API（必填） */
  list: (
    params: Record<string, unknown>,
  ) => Promise<T[] | { items: T[]; total: number }>;

  /**
   * Resource base path (required) / 资源基础路径（必填）
   * Used to auto-construct DELETE request: DELETE {resource}/{id}
   * 用于自动构造 DELETE 请求
   */
  resource: string;

  /**
   * Custom delete API (optional) / 自定义删除 API（可选）
   * If not provided, auto-constructs DELETE using resource path
   * 如不提供，使用 resource 路径自动构造
   */
  delete?: (id: number) => Promise<void>;

  /**
   * Toggle switch config (supports multiple) / 快捷开关配置（支持多个）
   * @example { is_active: toggleStatusApi }
   */
  toggles?: ToggleStatusConfig;
}

/** Recycle bin config / 回收站配置 */
export interface RecycleBinConfig {
  nameField?: string;
  columns?: Array<{ dataIndex: string; title: string; width?: number }>;
}

/** useCrudList configuration options / useCrudList 配置选项 */
export interface UseCrudListOptions<
  T extends object = Record<string, unknown>,
> {
  /**
   * Primary key field name / 主键字段名
   * @default 'id'
   * @example 'feature_code' | 'provider_id'
   */
  keyField?: string;
  /** API config (required) / API 配置（必填） */
  api: CrudListApiConfig<T>;

  /**
   * API response adapter / API 响应适配器
   * For non-standard API responses (e.g. array instead of {items, total})
   * 用于处理非标准 API 响应
   * @default Auto-detect: wraps array as { items: data, total: data.length }
   */
  responseAdapter?: (data: unknown) => { items: T[]; total: number };

  /** Form component / 表单组件 */
  formComponent?: Component;

  /** Form type: drawer or modal, default drawer / 表单类型 */
  formType?: 'drawer' | 'modal';

  /**
   * Default form values for create mode / 新建模式的表单默认值
   */
  formDefaults?: (() => Record<string, unknown>) | Record<string, unknown>;

  /**
   * Client-side filter function / 客户端过滤函数
   * When enabled, list loads all data at once, search filters on frontend
   * 启用后列表一次加载全量数据，搜索在前端过滤
   */
  clientFilter?: (item: T, keyword: string) => boolean;

  /** Fixed filter conditions (attached to every request) / 固定过滤条件 */
  defaultFilters?: Record<string, unknown>;

  /** Default sort field, default '-created_at' / 默认排序字段 */
  defaultSort?: string;

  /** Items per page, default 20 / 每页条数 */
  pageSize?: number;

  /** Whether pagination is enabled, default true / 是否启用分页 */
  pager?: boolean;

  /**
   * Auto-refresh interval (ms) / 自动刷新间隔（毫秒）
   * 0 or unset = no auto-refresh / 0 或不设置 = 不自动刷新
   */
  autoRefreshInterval?: number;

  /**
   * Whether to enable selection state (Master-Detail mode) / 是否启用选中状态
   * @default false
   */
  selectable?: boolean;

  /**
   * Default selection strategy / 默认选中策略
   * - 'first': auto-select first item after load / 加载后自动选中第一条
   * - 'none': no auto-selection / 不自动选中
   * @default 'first'
   */
  defaultSelect?: 'first' | 'none';

  /** i18n prefix (required) / i18n 前缀（必填） */
  i18nPrefix: string;

  /** Display name field, default 'name' / 用于显示的名称字段 */
  nameField?: keyof T & string;

  /** Create button permission code / 创建按钮权限码 */
  createPermission?: string;

  /**
   * Recycle bin config / 回收站配置
   * - true: enable with default config / 启用默认配置
   * - RecycleBinConfig: enable with custom config / 启用并自定义
   * - false/undefined: disabled / 不启用
   */
  recycleBin?: boolean | RecycleBinConfig;

  /** Custom action handlers / 自定义操作处理器 */
  customActions?: Record<string, (row: T) => void>;
}

/** useCrudList return value / useCrudList 返回值 */
export interface UseCrudListReturn<T extends object = Record<string, unknown>> {
  // === Reactive data / 响应式数据 ===
  list: Ref<T[]>;
  filteredList: ComputedRef<T[]>;
  total: Ref<number>;
  loading: Ref<boolean>;
  currentPage: Ref<number>;
  pageSize: Ref<number>;
  searchKeyword: Ref<string>;
  searchParams: Ref<Record<string, unknown>>;

  // === Selection state / 选中状态 ===
  selectedId: Ref<null | number | string>;
  selectedItem: ComputedRef<null | T>;

  // === Components / 组件 ===
  FormDrawer: Component | null;
  formApi:
    | null
    | ReturnType<typeof useVbenDrawer>[1]
    | ReturnType<typeof useVbenModal>[1];
  // === CRUD operations / CRUD 操作 ===
  loadList: () => Promise<void>;
  reload: () => Promise<void>;
  onCreate: () => void;
  onEdit: (row: T) => void;
  onDelete: (row: T) => Promise<void>;
  onToggleStatus: (newStatus: boolean, row: T) => Promise<boolean>;
  onToggleField: (
    fieldName: string,
    newStatus: boolean,
    row: T,
  ) => Promise<boolean>;
  onSelect: (row: T) => void;

  // === Search/pagination / 搜索/分页 ===
  onSearch: (params?: Record<string, unknown>) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;

  // === Recycle bin / 回收站 ===
  openRecycleBin: () => void;
  recycleBinCount: Ref<number>;

  // === Utilities / 辅助 ===
  isProcessing: (id: number | string) => boolean;
  handleMenuAction: (code: string, row: T) => void;

  // === Lifecycle / 生命周期 ===
  startAutoRefresh: () => void;
  stopAutoRefresh: () => void;
}

// ============================================================
// Dependency block error code / 依赖阻止错误码
// ============================================================
const DEPENDENCY_BLOCKED_CODE = 4221;

// ============================================================
// Default response adapter: auto-detect array/paginated format
// 默认响应适配器：自动检测数组/分页格式
// ============================================================
function defaultResponseAdapter<T>(data: unknown): {
  items: T[];
  total: number;
} {
  if (Array.isArray(data)) {
    return { items: data as T[], total: data.length };
  }
  const obj = data as Record<string, unknown>;
  if (obj && Array.isArray(obj.items)) {
    return {
      items: obj.items as T[],
      total: (obj.total as number) ?? obj.items.length,
    };
  }
  return { items: [], total: 0 };
}

// ============================================================
// Date range processing (reused from useCrudPage)
// 日期范围处理（复用自 useCrudPage）
// ============================================================
function processFormValues(
  formValues: Record<string, unknown>,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(formValues)) {
    if (key.startsWith('_dateRange_') && Array.isArray(value)) {
      const field = key.replace('_dateRange_', '');
      const [startDate, endDate] = value;
      if (startDate && endDate) {
        result[`filter[${field}][between]`] = `${startDate},${endDate}`;
      } else if (startDate) {
        result[`filter[${field}][gte]`] = startDate;
      } else if (endDate) {
        result[`filter[${field}][lte]`] = endDate;
      }
    } else if (value !== undefined && value !== null && value !== '') {
      result[key] = value;
    }
  }

  return result;
}

// ============================================================
// useCrudList implementation / useCrudList 实现
// ============================================================

export function useCrudList<T extends object = Record<string, unknown>>(
  options: UseCrudListOptions<T>,
): UseCrudListReturn<T> {
  const {
    api,
    responseAdapter = defaultResponseAdapter,
    formComponent,
    formType = 'drawer',
    formDefaults,
    clientFilter,
    defaultFilters = {},
    defaultSort = '-created_at',
    pageSize: initialPageSize = 20,
    pager = true,
    autoRefreshInterval = 0,
    selectable = false,
    defaultSelect = 'first',
    i18nPrefix,
    keyField = 'id',
    nameField = 'name' as keyof T & string,
    customActions = {},
  } = options;

  /** Get row primary key value / 获取行主键值 */
  function getRowKey(row: T): number | string {
    return (row as Record<string, unknown>)[keyField] as number | string;
  }

  // ==================== Reactive state / 响应式状态 ====================
  const list = ref<T[]>([]) as Ref<T[]>;
  const total = ref(0);
  const loading = ref(false);
  const currentPage = ref(1);
  const pageSize = ref(initialPageSize);
  const searchKeyword = ref('');
  const searchParams = ref<Record<string, unknown>>({});

  // ==================== Selection state / 选中状态 ====================
  const selectedId = ref<null | number | string>(null);
  const selectedItem = computed<null | T>(() => {
    if (!selectable || selectedId.value === null) return null;
    return (
      list.value.find((item) => getRowKey(item) === selectedId.value) ?? null
    );
  });

  function onSelect(row: T) {
    selectedId.value = getRowKey(row);
  }

  // ==================== Client-side filter / 客户端过滤 ====================
  const filteredList = computed<T[]>(() => {
    if (!clientFilter || !searchKeyword.value.trim()) {
      return list.value;
    }
    const kw = searchKeyword.value.toLowerCase().trim();
    return list.value.filter((item) => clientFilter(item, kw));
  });

  // ==================== List loading / 列表加载 ====================
  async function loadList() {
    loading.value = true;
    try {
      let result: { items: T[]; total: number };

      if (clientFilter) {
        // Client filter mode: load all data / 客户端过滤模式：加载全量数据
        const rawData = await api.list({
          'page[size]': 9999,
          sort: defaultSort,
          ...defaultFilters,
        });
        result = responseAdapter(rawData);
      } else {
        // Server-side pagination mode / 服务端分页模式
        const processedParams = processFormValues(searchParams.value);
        const params: Record<string, unknown> = {
          ...processedParams,
          ...defaultFilters,
          sort: defaultSort,
        };
        if (pager) {
          params['page[number]'] = currentPage.value;
          params['page[size]'] = pageSize.value;
        } else {
          params['page[size]'] = 9999;
        }
        const rawData = await api.list(params);
        result = responseAdapter(rawData);
      }

      list.value = result.items;
      total.value = result.total;

      // Selection state handling / 选中状态处理
      if (
        selectable &&
        list.value.length > 0 &&
        (selectedId.value === null ||
          !list.value.some((item) => getRowKey(item) === selectedId.value)) &&
        defaultSelect === 'first'
      ) {
        const firstItem = list.value[0];
        if (firstItem) {
          selectedId.value = getRowKey(firstItem);
        }
      }
    } catch {
      list.value = [];
      total.value = 0;
    } finally {
      loading.value = false;
    }
  }

  async function reload() {
    currentPage.value = 1;
    await loadList();
  }

  // ==================== Search / 搜索 ====================
  function onSearch(params?: Record<string, unknown>) {
    if (params) {
      searchParams.value = params;
    }
    currentPage.value = 1;
    loadList();
  }

  function onPageChange(page: number) {
    currentPage.value = page;
    loadList();
  }

  function onPageSizeChange(size: number) {
    pageSize.value = size;
    currentPage.value = 1;
    loadList();
  }

  // ==================== Form popup / 表单弹窗 ====================
  let FormPopup:
    | null
    | ReturnType<typeof useVbenDrawer>[0]
    | ReturnType<typeof useVbenModal>[0] = null;
  let formPopupApi:
    | null
    | ReturnType<typeof useVbenDrawer>[1]
    | ReturnType<typeof useVbenModal>[1] = null;

  if (formComponent) {
    if (formType === 'modal') {
      const [ModalComp, modalApi] = useVbenModal({
        connectedComponent: formComponent,
        destroyOnClose: true,
      });
      FormPopup = ModalComp;
      formPopupApi = modalApi;
    } else {
      const [DrawerComp, drawerApi] = useVbenDrawer({
        connectedComponent: formComponent,
        destroyOnClose: true,
      });
      FormPopup = DrawerComp;
      formPopupApi = drawerApi;
    }
  }

  function onCreate() {
    const defaults =
      typeof formDefaults === 'function' ? formDefaults() : formDefaults;
    formPopupApi
      ?.setData({
        mode: 'add',
        _resource: api.resource,
        _defaults: defaults,
      })
      .open();
  }

  function onEdit(row: T) {
    formPopupApi
      ?.setData({ ...row, mode: 'edit', _resource: api.resource })
      .open();
  }

  // ==================== Debounce state / 防抖状态 ====================
  const processingIds = ref<Set<number | string>>(new Set());

  function isProcessing(id: number | string): boolean {
    return processingIds.value.has(id);
  }

  function setProcessing(id: number | string, processing: boolean) {
    if (processing) {
      processingIds.value.add(id);
    } else {
      processingIds.value.delete(id);
    }
  }

  // ==================== Delete / 删除 ====================
  async function onDelete(row: T) {
    const rowId = getRowKey(row);
    if (isProcessing(rowId)) return;

    setProcessing(rowId, true);
    try {
      await (api.delete
        ? api.delete(rowId as number)
        : requestClient.delete(`${api.resource}/${rowId}`, {
            loading: true,
            showCodeMessage: false,
            showSuccessMessage: true,
            successMessage: $t(`${i18nPrefix}.messages.deleteSuccess`),
          }));
      await loadList();
    } catch (error: unknown) {
      const resp = (error as Record<string, unknown>)?.response as
        | Record<string, unknown>
        | undefined;
      const data = resp?.data as Record<string, unknown> | undefined;
      if (data?.code === DEPENDENCY_BLOCKED_CODE && data?.dependencies) {
        const displayName = String(row[nameField] || rowId);
        showDependencyBlock(
          data.dependencies as DependencyGroup[],
          displayName,
        );
      } else if (data?.message) {
        message.error(String(data.message));
      }
    } finally {
      setProcessing(rowId, false);
    }
  }

  // ==================== Toggle status / Toggle 状态 ====================
  async function onToggleField(
    fieldName: string,
    newStatus: boolean,
    row: T,
  ): Promise<boolean> {
    const rowId = getRowKey(row);
    if (isProcessing(rowId)) return false;

    const toggleApi = api.toggles?.[fieldName] as ToggleStatusApi | undefined;
    if (!toggleApi) return false;

    const displayName = String(row[nameField] || rowId);
    const action = newStatus
      ? $t('admin.common.enable')
      : $t('admin.common.disable');

    try {
      await new Promise<void>((resolve, reject) => {
        Modal.confirm({
          title: $t(`${i18nPrefix}.messages.toggleStatusTitle`),
          content: $t(`${i18nPrefix}.messages.toggleStatusConfirm`, {
            action,
            name: displayName,
          }),
          onOk: () => resolve(),
          onCancel: () => reject(new Error('cancelled')),
        });
      });

      setProcessing(rowId, true);
      try {
        await toggleApi(rowId, { [fieldName]: newStatus });
        message.success(`${action}${$t('ui.actionMessage.operationSuccess')}`);
        await loadList();
        return true;
      } finally {
        setProcessing(rowId, false);
      }
    } catch {
      return false;
    }
  }

  async function onToggleStatus(newStatus: boolean, row: T): Promise<boolean> {
    return onToggleField('is_active', newStatus, row);
  }

  // ==================== Recycle bin / 回收站 ====================
  const recycleBinCount = ref(0);

  function openRecycleBin() {
    // noop — page manages RecycleBinDrawer ref and open() / 页面自行管理
  }

  // ==================== Action dispatch / 操作分发 ====================
  function handleMenuAction(code: string, row: T) {
    const customAction = customActions[code];
    if (customAction) {
      customAction(row);
      return;
    }

    switch (code) {
      case 'delete': {
        onDelete(row);
        break;
      }
      case 'edit': {
        onEdit(row);
        break;
      }
    }
  }

  // ==================== Auto-refresh / 自动刷新 ====================
  let refreshTimer: null | ReturnType<typeof setInterval> = null;

  function startAutoRefresh() {
    stopAutoRefresh();
    if (autoRefreshInterval > 0) {
      refreshTimer = setInterval(() => {
        // Avoid stacking requests on hidden pages or slow requests / 避免隐藏页面或慢请求场景下叠加请求
        if (document.hidden || loading.value) return;
        loadList();
      }, autoRefreshInterval);
    }
  }

  function stopAutoRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  // ==================== Lifecycle / 生命周期 ====================
  onMounted(() => {
    loadList();
    if (autoRefreshInterval > 0) {
      startAutoRefresh();
    }
  });

  // Stop auto-refresh when KeepAlive page deactivates / KeepAlive 页面切走时停止自动刷新
  onDeactivated(() => {
    stopAutoRefresh();
  });

  // Resume auto-refresh when KeepAlive page reactivates / KeepAlive 页面恢复时再启动
  onActivated(() => {
    if (autoRefreshInterval > 0) {
      startAutoRefresh();
    }
  });

  onBeforeUnmount(() => {
    stopAutoRefresh();
  });

  // ==================== Return / 返回 ====================
  return {
    // Reactive data / 响应式数据
    list,
    filteredList,
    total,
    loading,
    currentPage,
    pageSize,
    searchKeyword,
    searchParams,

    // Selection state / 选中状态
    selectedId,
    selectedItem,

    // Components / 组件
    FormDrawer: FormPopup,
    formApi: formPopupApi,

    // CRUD operations / CRUD 操作
    loadList,
    reload,
    onCreate,
    onEdit,
    onDelete,
    onToggleStatus,
    onToggleField,
    onSelect,

    // Search/pagination / 搜索/分页
    onSearch,
    onPageChange,
    onPageSizeChange,

    // Recycle bin / 回收站
    openRecycleBin,
    recycleBinCount,

    // Utilities / 辅助
    isProcessing,
    handleMenuAction,

    // Lifecycle / 生命周期
    startAutoRefresh,
    stopAutoRefresh,
  };
}
