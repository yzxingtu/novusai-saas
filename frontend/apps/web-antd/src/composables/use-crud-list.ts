/**
 * 声明式 CRUD 列表 Composable — 无渲染数据层
 *
 * 提供完整的列表数据管理能力（加载、搜索、分页、CRUD、回收站），
 * 但不绑定任何渲染组件（VxeTable / Card / 等），
 * 页面可自由选择渲染方式（卡片网格、配置面板、Master-Detail 等）。
 *
 * @example 卡片网格
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
 * @example Master-Detail（配合 selectable）
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

/** 命令式显示依赖阻止弹窗（无需组件 ref） */
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
// 类型定义
// ============================================================

/** 切换状态 API 类型 */
export type ToggleStatusApi = (
  id: number | string,
  data: Record<string, unknown>,
) => Promise<unknown>;

/** 切换状态配置 */
export type ToggleStatusConfig = Record<string, ToggleStatusApi>;

/** API 配置 */
export interface CrudListApiConfig<T = unknown> {
  /** 列表查询 API（必填） */
  list: (
    params: Record<string, unknown>,
  ) => Promise<T[] | { items: T[]; total: number }>;

  /**
   * 资源基础路径（必填）
   * 用于自动构造 DELETE 请求：DELETE {resource}/{id}
   */
  resource: string;

  /**
   * 自定义删除 API（可选）
   * 如不提供，将使用 resource 路径自动构造 DELETE 请求
   */
  delete?: (id: number) => Promise<void>;

  /**
   * 快捷开关配置（支持多个）
   * @example { is_active: toggleStatusApi }
   */
  toggles?: ToggleStatusConfig;
}

/** 回收站配置 */
export interface RecycleBinConfig {
  nameField?: string;
  columns?: Array<{ dataIndex: string; title: string; width?: number }>;
}

/** useCrudList 配置选项 */
export interface UseCrudListOptions<
  T extends object = Record<string, unknown>,
> {
  /**
   * 主键字段名
   * @default 'id'
   * @example 'feature_code' | 'provider_id'
   */
  keyField?: string;
  /** API 配置（必填） */
  api: CrudListApiConfig<T>;

  /**
   * API 响应适配器
   * 用于处理非标准 API 响应（如返回数组而非 {items, total}）
   * @default 自动检测：数组包装为 { items: data, total: data.length }
   */
  responseAdapter?: (data: unknown) => { items: T[]; total: number };

  /** 表单组件 */
  formComponent?: Component;

  /** 表单类型：drawer 或 modal，默认 drawer */
  formType?: 'drawer' | 'modal';

  /**
   * 新建模式的表单默认值
   */
  formDefaults?: (() => Record<string, unknown>) | Record<string, unknown>;

  /**
   * 客户端过滤函数
   * 启用后，列表一次加载全量数据，搜索在前端过滤
   */
  clientFilter?: (item: T, keyword: string) => boolean;

  /** 固定过滤条件（每次请求都会附带） */
  defaultFilters?: Record<string, unknown>;

  /** 默认排序字段，默认 '-created_at' */
  defaultSort?: string;

  /** 每页条数，默认 20 */
  pageSize?: number;

  /** 是否启用分页，默认 true */
  pager?: boolean;

  /**
   * 自动刷新间隔（毫秒）
   * 0 或不设置 = 不自动刷新
   */
  autoRefreshInterval?: number;

  /**
   * 是否启用选中状态（Master-Detail 模式）
   * @default false
   */
  selectable?: boolean;

  /**
   * 默认选中策略
   * - 'first': 加载后自动选中第一条
   * - 'none': 不自动选中
   * @default 'first'
   */
  defaultSelect?: 'first' | 'none';

  /** i18n 前缀（必填） */
  i18nPrefix: string;

  /** 用于显示的名称字段，默认 'name' */
  nameField?: keyof T & string;

  /** 创建按钮权限码 */
  createPermission?: string;

  /**
   * 回收站配置
   * - true: 启用回收站，使用默认配置
   * - RecycleBinConfig: 启用并自定义
   * - false/undefined: 不启用
   */
  recycleBin?: boolean | RecycleBinConfig;

  /** 自定义操作处理器 */
  customActions?: Record<string, (row: T) => void>;
}

/** useCrudList 返回值 */
export interface UseCrudListReturn<T extends object = Record<string, unknown>> {
  // === 响应式数据 ===
  list: Ref<T[]>;
  filteredList: ComputedRef<T[]>;
  total: Ref<number>;
  loading: Ref<boolean>;
  currentPage: Ref<number>;
  pageSize: Ref<number>;
  searchKeyword: Ref<string>;
  searchParams: Ref<Record<string, unknown>>;

  // === 选中状态 ===
  selectedId: Ref<null | number | string>;
  selectedItem: ComputedRef<null | T>;

  // === 组件 ===
  FormDrawer: Component | null;
  formApi:
    | null
    | ReturnType<typeof useVbenDrawer>[1]
    | ReturnType<typeof useVbenModal>[1];
  // === CRUD 操作 ===
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

  // === 搜索/分页 ===
  onSearch: (params?: Record<string, unknown>) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;

  // === 回收站 ===
  openRecycleBin: () => void;
  recycleBinCount: Ref<number>;

  // === 辅助 ===
  isProcessing: (id: number | string) => boolean;
  handleMenuAction: (code: string, row: T) => void;

  // === 生命周期 ===
  startAutoRefresh: () => void;
  stopAutoRefresh: () => void;
}

// ============================================================
// 依赖阻止错误码
// ============================================================
const DEPENDENCY_BLOCKED_CODE = 4221;

// ============================================================
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
// useCrudList 实现
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

  /** 获取行主键值 */
  function getRowKey(row: T): number | string {
    return (row as Record<string, unknown>)[keyField] as number | string;
  }

  // ==================== 响应式状态 ====================
  const list = ref<T[]>([]) as Ref<T[]>;
  const total = ref(0);
  const loading = ref(false);
  const currentPage = ref(1);
  const pageSize = ref(initialPageSize);
  const searchKeyword = ref('');
  const searchParams = ref<Record<string, unknown>>({});

  // ==================== 选中状态 ====================
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

  // ==================== 客户端过滤 ====================
  const filteredList = computed<T[]>(() => {
    if (!clientFilter || !searchKeyword.value.trim()) {
      return list.value;
    }
    const kw = searchKeyword.value.toLowerCase().trim();
    return list.value.filter((item) => clientFilter(item, kw));
  });

  // ==================== 列表加载 ====================
  async function loadList() {
    loading.value = true;
    try {
      let result: { items: T[]; total: number };

      if (clientFilter) {
        // 客户端过滤模式：加载全量数据
        const rawData = await api.list({
          'page[size]': 9999,
          sort: defaultSort,
          ...defaultFilters,
        });
        result = responseAdapter(rawData);
      } else {
        // 服务端分页模式
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

      // 选中状态处理
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

  // ==================== 搜索 ====================
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

  // ==================== 表单弹窗 ====================
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

  // ==================== 防抖状态 ====================
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

  // ==================== 删除 ====================
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

  // ==================== Toggle 状态 ====================
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

  // ==================== 回收站 ====================
  const recycleBinCount = ref(0);

  function openRecycleBin() {
    // noop — 页面自行管理 RecycleBinDrawer ref 和 open()
  }

  // ==================== 操作分发 ====================
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

  // ==================== 自动刷新 ====================
  let refreshTimer: null | ReturnType<typeof setInterval> = null;

  function startAutoRefresh() {
    stopAutoRefresh();
    if (autoRefreshInterval > 0) {
      refreshTimer = setInterval(() => {
        // 避免隐藏页面或慢请求场景下叠加请求，导致主线程与网络风暴
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

  // ==================== 生命周期 ====================
  onMounted(() => {
    loadList();
    if (autoRefreshInterval > 0) {
      startAutoRefresh();
    }
  });

  // KeepAlive 页面切走时停止自动刷新，避免后台持续轮询
  onDeactivated(() => {
    stopAutoRefresh();
  });

  // KeepAlive 页面恢复时再启动自动刷新
  onActivated(() => {
    if (autoRefreshInterval > 0) {
      startAutoRefresh();
    }
  });

  onBeforeUnmount(() => {
    stopAutoRefresh();
  });

  // ==================== 返回 ====================
  return {
    // 响应式数据
    list,
    filteredList,
    total,
    loading,
    currentPage,
    pageSize,
    searchKeyword,
    searchParams,

    // 选中状态
    selectedId,
    selectedItem,

    // 组件
    FormDrawer: FormPopup,
    formApi: formPopupApi,

    // CRUD 操作
    loadList,
    reload,
    onCreate,
    onEdit,
    onDelete,
    onToggleStatus,
    onToggleField,
    onSelect,

    // 搜索/分页
    onSearch,
    onPageChange,
    onPageSizeChange,

    // 回收站
    openRecycleBin,
    recycleBinCount,

    // 辅助
    isProcessing,
    handleMenuAction,

    // 生命周期
    startAutoRefresh,
    stopAutoRefresh,
  };
}
