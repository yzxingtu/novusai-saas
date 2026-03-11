/**
 * Declarative CRUD list page composable
 * 声明式 CRUD 列表页 Composable
 *
 * Unifies table, form popup, CRUD operations, pagination, sorting, etc.
 * Users only need to care about: column definitions, API, form component.
 * 将表格、表单弹窗、CRUD 操作、分页、排序等统一封装，
 * 用户只需关心：列定义、API、表单组件。
 *
 * @example
 * ```ts
 * import { adminApi as admin } from '#/api';
 *
 * const { Grid, FormDrawer, onCreate, onRefresh } = useCrudPage<AdminInfo>({
 *   api: {
 *     list: admin.getAdminListApi,
 *     resource: '/admin/admins',
 *     toggles: { is_active: admin.toggleAdminStatusApi },
 *   },
 *   columns: useColumns,
 *   searchSchema: useGridFormSchema(),
 *   formComponent: Form,
 *   i18nPrefix: 'admin.system.admin',
 *   nameField: 'username',
 * });
 * ```
 */

import type {
  BaseRow,
  FormMode,
  OnActionClickParams,
  RecycleBinConfig,
  ToggleStatusApi,
  UseCrudPageOptions,
} from './types';

import { defineComponent, h, ref } from 'vue';

import { useVbenDrawer, useVbenModal } from '@vben/common-ui';

import { message, Modal } from 'ant-design-vue';

import DependencyBlockModal from '#/components/business/dependency-block-modal/index.vue';
import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

import { CrudGrid, RecycleBinDrawer, useExportModal } from './components';
import { useGridSearchFormOptions, useVbenVxeGrid } from './use-vxe-grid';

/** Dependency blocked error code / 依赖阻止错误码 */
const DEPENDENCY_BLOCKED_CODE = 4221;

/**
 * Declarative CRUD list page composable / 声明式 CRUD 列表页 Composable
 */
export function useCrudPage<T extends BaseRow = BaseRow>(
  options: UseCrudPageOptions<T>,
) {
  const {
    api,
    columns,
    searchSchema,
    formComponent,
    formType = 'drawer',
    formDefaults,
    i18nPrefix,
    nameField = 'name' as keyof T & string,
    defaultSort = '-created_at',
    rowHeight = 56,
    stripe = true,
    pager = true,
    toolbar = {
      custom: true,
      export: true,
      refresh: true,
      search: true,
      zoom: true,
    },
    customActions = {},
    createPermission,
    recycleBin,
    gridOptions: extraGridOptions = {},
  } = options;

  // ==================== Recycle bin config / 回收站配置 ====================
  const recycleBinEnabled = !!recycleBin;
  const recycleBinConfig: RecycleBinConfig =
    typeof recycleBin === 'object' ? recycleBin : {};
  const recycleBinRef = ref<InstanceType<typeof RecycleBinDrawer> | null>(null);

  // ==================== Dependency block modal / 依赖阻止弹窗 ====================
  const depBlockRef = ref<InstanceType<typeof DependencyBlockModal> | null>(
    null,
  );

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
      const [Drawer, drawerApi] = useVbenDrawer({
        connectedComponent: formComponent,
        destroyOnClose: true,
      });
      FormPopup = Drawer;
      formPopupApi = drawerApi;
    }
  }

  // ==================== Export modal / 导出弹窗 ====================
  // Pre-declare gridApi (for closure reference) / 前置声明 gridApi（用于闭包引用）
  let gridApi: ReturnType<typeof useVbenVxeGrid>[1];

  // Export modal / 导出弹窗
  const { ExportModal, openExportModal } = useExportModal(() => gridApi?.grid);

  // ==================== CRUD Operations / CRUD 操作 ====================

  /** Refresh list / 刷新列表 */
  function onRefresh() {
    gridApi?.query();
  }

  /** Reload list (back to first page) / 重载列表（回到第一页） */
  function onReload() {
    gridApi?.reload();
  }

  /** Create / 新建 */
  function onCreate() {
    const defaults =
      typeof formDefaults === 'function' ? formDefaults() : formDefaults;
    formPopupApi
      ?.setData({
        mode: 'add' as FormMode,
        _resource: api.resource,
        _defaults: defaults,
      })
      .open();
  }

  /** Edit / 编辑 */
  function onEdit(row: T) {
    formPopupApi
      ?.setData({ ...row, mode: 'edit' as FormMode, _resource: api.resource })
      .open();
  }

  // Debounce state: track in-progress operations / 防抖状态：记录正在处理的操作
  const processingIds = ref<Set<number | string>>(new Set());

  /** Check if processing (debounce) / 检查是否正在处理中（防抖） */
  function isProcessing(id: number | string): boolean {
    return processingIds.value.has(id);
  }

  /** Set processing state / 设置处理状态 */
  function setProcessing(id: number | string, processing: boolean) {
    if (processing) {
      processingIds.value.add(id);
    } else {
      processingIds.value.delete(id);
    }
  }

  /**
   * Delete (auto-constructs DELETE {resource}/{id} request)
   * 删除（自动构造 DELETE {resource}/{id} 请求）
   * Note: CellOperation renderer already provides Popconfirm, this directly executes delete
   * 注意：CellOperation 渲染器已经提供了 Popconfirm 确认，此处直接执行删除
   */
  async function onDelete(row: T) {
    // Debounce: return if already processing / 防抖：如果正在处理中，直接返回
    if (isProcessing(row.id)) return;

    setProcessing(row.id, true);
    try {
      // Auto-construct DELETE request: DELETE {resource}/{id} / 自动构造 DELETE 请求
      // Disable default error message, handled by catch below for 4221 / 关闭默认错误消息，由下方 catch 手动处理 4221
      await requestClient.delete(`${api.resource}/${row.id}`, {
        loading: true,
        showCodeMessage: false,
        showSuccessMessage: true,
        successMessage: $t(`${i18nPrefix}.messages.deleteSuccess`),
      });
      onRefresh();
      // Refresh recycle bin count / 刷新回收站计数
      if (recycleBinEnabled) {
        recycleBinRef.value?.refreshCount();
      }
    } catch (error: unknown) {
      const resp = (error as any)?.response?.data;
      if (resp?.code === DEPENDENCY_BLOCKED_CODE && resp?.dependencies) {
        // 4221: Dependency blocked → show dependency details modal / 依赖阻止 → 弹出依赖详情弹窗
        const displayName = String(row[nameField] || row.id);
        depBlockRef.value?.open(resp.dependencies, displayName);
      } else if (resp?.message) {
        // Other business errors → show error message / 其他业务错误 → 显示错误消息
        message.error(resp.message);
      }
    } finally {
      setProcessing(row.id, false);
    }
  }

  /**
   * Toggle status (supports multiple fields)
   * 切换状态（支持多个字段）
   * @param fieldName Field name, e.g. 'is_active', 'is_visible' / 字段名
   * @param newStatus New status value / 新状态值
   * @param row Row data / 行数据
   */
  async function onToggleField(
    fieldName: string,
    newStatus: boolean,
    row: T,
  ): Promise<boolean> {
    // Debounce: return if already processing / 防抖：如果正在处理中，直接返回
    if (isProcessing(row.id)) return false;

    const toggleApi = api.toggles?.[fieldName] as ToggleStatusApi | undefined;
    if (!toggleApi) {
      return false;
    }

    const displayName = String(row[nameField] || row.id);
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

      setProcessing(row.id, true);
      try {
        await toggleApi(row.id, { [fieldName]: newStatus });
        message.success(`${action}${$t('ui.actionMessage.operationSuccess')}`);
        gridApi.reload();
        return true;
      } finally {
        setProcessing(row.id, false);
      }
    } catch {
      return false;
    }
  }

  /**
   * Toggle is_active status / 切换 is_active 状态
   */
  async function onToggleStatus(newStatus: boolean, row: T): Promise<boolean> {
    return onToggleField('is_active', newStatus, row);
  }

  // ==================== Action Handlers / 操作处理器 ====================

  /** Action button click handler / 操作按钮点击处理 */
  function handleActionClick(e: OnActionClickParams<T>) {
    // Custom actions take priority over built-in / 自定义操作优先于内置操作
    const customAction = customActions[e.code];
    if (customAction) {
      customAction(e.row);
      return;
    }

    switch (e.code) {
      case 'delete': {
        onDelete(e.row);
        break;
      }
      case 'edit': {
        onEdit(e.row);
        break;
      }
      default: {
        break;
      }
    }
  }

  /** Status toggle handler (for column definitions) / 状态切换处理（供列定义使用） */
  function handleToggleStatus(newStatus: boolean, row: T) {
    return onToggleStatus(newStatus, row);
  }

  /**
   * Create toggle handler for specified field (for column definitions)
   * 创建指定字段的 toggle 处理函数（供列定义使用）
   * @param fieldName Field name, e.g. 'is_active', 'is_visible' / 字段名
   */
  function createToggleHandler(fieldName: string) {
    return (newStatus: boolean, row: T) =>
      onToggleField(fieldName, newStatus, row);
  }

  // ==================== Table Config / 表格配置 ====================

  // Build toolbar config / 构建工具栏配置
  const showExportButton = toolbar.export !== false;
  const toolbarConfig = {
    ...toolbar,
    export: false, // Disable native export, use custom export button / 禁用原生导出，使用自定义导出按钮
    refresh: false, // Disable native refresh, CrudGrid renders custom left-side / 禁用原生刷新，CrudGrid 左侧自定义渲染
  };

  // Create button label: defaults to i18nPrefix + '.create' / 创建按钮文案：默认取 i18nPrefix + '.create'
  const createLabel = formComponent ? $t(`${i18nPrefix}.create`) : '';

  /**
   * Process form params, convert date ranges and other special fields.
   * 处理表单参数，转换日期范围等特殊字段
   * Date ranges use between operator: filter[field][between]=start,end
   * 日期范围使用 between 操作符: filter[field][between]=start,end
   */
  function processFormValues(formValues: Record<string, any>) {
    const result: Record<string, any> = {};

    for (const [key, value] of Object.entries(formValues)) {
      // Process date range fields: _dateRange_xxx -> filter[xxx][between]=start,end / 处理日期范围字段
      if (key.startsWith('_dateRange_') && Array.isArray(value)) {
        const field = key.replace('_dateRange_', '');
        const [startDate, endDate] = value;
        if (startDate && endDate) {
          // Use between operator, format: filter[field][between]=start,end / 使用 between 操作符
          result[`filter[${field}][between]`] = `${startDate},${endDate}`;
        } else if (startDate) {
          // Only start date, use gte / 只有开始日期，使用 gte
          result[`filter[${field}][gte]`] = startDate;
        } else if (endDate) {
          // Only end date, use lte / 只有结束日期，使用 lte
          result[`filter[${field}][lte]`] = endDate;
        }
      } else if (value !== undefined && value !== null && value !== '') {
        // Filter empty values / 过滤空值
        result[key] = value;
      }
    }

    return result;
  }

  const gridOptions = {
    columns: columns(handleActionClick, handleToggleStatus),
    stripe,
    keepSource: true,
    pagerConfig: { enabled: pager },
    proxyConfig: {
      ajax: {
        query: async ({ page }: any, formValues: any) => {
          const processedValues = processFormValues(formValues);
          return await api.list({
            ...processedValues,
            'page[number]': page.currentPage,
            'page[size]': page.pageSize,
            sort: defaultSort,
          });
        },
      },
    },
    cellConfig: { height: rowHeight },
    rowConfig: { keyField: 'id' },
    toolbarConfig,
    ...extraGridOptions,
  };

  // Create table / 创建表格
  const [OriginalGrid, _gridApi] = useVbenVxeGrid({
    formOptions: searchSchema
      ? useGridSearchFormOptions(searchSchema)
      : undefined,
    gridOptions,
  });

  // Assign to closure reference / 赋值给闭包引用
  gridApi = _gridApi;

  /** Open recycle bin / 打开回收站 */
  function openRecycleBin() {
    recycleBinRef.value?.open();
  }

  // Wrap Grid component, auto-add export button, recycle bin button and popups / 包装 Grid 组件，自动添加导出按钮、回收站按钮和弹窗
  const Grid = defineComponent({
    name: 'CrudPageGrid',
    inheritAttrs: false,
    setup(_, { attrs, slots }) {
      return () => {
        const children = [
          h(
            CrudGrid,
            {
              grid: OriginalGrid,
              showExport: showExportButton,
              showRecycleBin: recycleBinEnabled,
              recycleBinCount: recycleBinRef.value?.deletedCount ?? 0,
              onExport: openExportModal,
              onRecycleBin: openRecycleBin,
              onRefresh,
              ...(formComponent && createPermission
                ? {
                    onCreate,
                    createPermission,
                    createLabel,
                  }
                : {}),
              ...attrs,
            },
            slots,
          ),
          h(ExportModal),
        ];

        // Render recycle bin drawer / 渲染回收站抽屉
        if (recycleBinEnabled) {
          children.push(
            h(RecycleBinDrawer, {
              ref: recycleBinRef,
              resource: api.resource,
              nameField: recycleBinConfig.nameField ?? (nameField as string),
              columns: recycleBinConfig.columns,
              onRestored: onRefresh,
            }),
          );
        }

        // Render dependency block modal / 渲染依赖阻止弹窗
        children.push(h(DependencyBlockModal, { ref: depBlockRef }));

        return h('div', { class: 'crud-page-grid h-full' }, children);
      };
    },
  });

  return {
    // Components / 组件
    Grid,
    gridApi,
    FormDrawer: FormPopup,
    formApi: formPopupApi,
    ExportModal,

    // CRUD Operations / CRUD 操作
    onCreate,
    onEdit,
    onDelete,
    onToggleStatus,
    onToggleField,
    onRefresh,
    onReload,

    // Export / 导出
    openExportModal,

    // Handlers / 处理器
    handleActionClick,
    handleToggleStatus,
    createToggleHandler,

    // Recycle bin / 回收站
    openRecycleBin,
    recycleBinRef,
  };
}
