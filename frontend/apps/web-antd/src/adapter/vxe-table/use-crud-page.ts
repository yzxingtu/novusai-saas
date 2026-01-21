/**
 * 声明式 CRUD 列表页 Composable
 *
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
  ToggleStatusApi,
  UseCrudPageOptions,
} from './types';

import { defineComponent, h, ref } from 'vue';

import { useVbenDrawer, useVbenModal } from '@vben/common-ui';

import { message, Modal } from 'ant-design-vue';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

import { CrudGrid, useExportModal } from './components';
import { useGridSearchFormOptions, useVbenVxeGrid } from './use-vxe-grid';

/**
 * 声明式 CRUD 列表页 Composable
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
    rowHeight = 64,
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
  } = options;

  // ==================== 表单弹窗 ====================
  let FormPopup: null | ReturnType<typeof useVbenDrawer>[0] = null;
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
      FormPopup = ModalComp as any;
      formPopupApi = modalApi as any;
    } else {
      const [Drawer, drawerApi] = useVbenDrawer({
        connectedComponent: formComponent,
        destroyOnClose: true,
      });
      FormPopup = Drawer;
      formPopupApi = drawerApi;
    }
  }

  // ==================== 导出弹窗 ====================
  // 前置声明 gridApi（用于闭包引用）
  let gridApi: ReturnType<typeof useVbenVxeGrid>[1];

  // 导出弹窗
  const { ExportModal, openExportModal } = useExportModal(() => gridApi?.grid);

  // ==================== CRUD 操作 ====================

  /** 刷新列表 */
  function onRefresh() {
    gridApi?.query();
  }

  /** 重载列表（回到第一页） */
  function onReload() {
    gridApi?.reload();
  }

  /** 新建 */
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

  /** 编辑 */
  function onEdit(row: T) {
    formPopupApi
      ?.setData({ ...row, mode: 'edit' as FormMode, _resource: api.resource })
      .open();
  }

  // 防抖状态：记录正在处理的操作
  const processingIds = ref<Set<number | string>>(new Set());

  /** 检查是否正在处理中（防抖） */
  function isProcessing(id: number | string): boolean {
    return processingIds.value.has(id);
  }

  /** 设置处理状态 */
  function setProcessing(id: number | string, processing: boolean) {
    if (processing) {
      processingIds.value.add(id);
    } else {
      processingIds.value.delete(id);
    }
  }

  /**
   * 删除（自动构造 DELETE {resource}/{id} 请求）
   * 注意：CellOperation 渲染器已经提供了 Popconfirm 确认，此处直接执行删除
   */
  async function onDelete(row: T) {
    // 防抖：如果正在处理中，直接返回
    if (isProcessing(row.id)) return;

    setProcessing(row.id, true);
    try {
      // 自动构造 DELETE 请求：DELETE {resource}/{id}
      await requestClient.delete(`${api.resource}/${row.id}`, {
        loading: true,
        showCodeMessage: true,
        showSuccessMessage: true,
        successMessage: $t(`${i18nPrefix}.messages.deleteSuccess`),
      });
      onRefresh();
    } finally {
      setProcessing(row.id, false);
    }
  }

  /**
   * 切换状态（支持多个字段）
   * @param fieldName 字段名，如 'is_active', 'is_visible'
   * @param newStatus 新状态值
   * @param row 行数据
   */
  async function onToggleField(
    fieldName: string,
    newStatus: boolean,
    row: T,
  ): Promise<boolean> {
    // 防抖：如果正在处理中，直接返回
    if (isProcessing(row.id)) return false;

    const toggleApi = api.toggles?.[fieldName] as ToggleStatusApi | undefined;
    if (!toggleApi) {
      console.warn(
        `[useCrudPage] toggle API not found for field: ${fieldName}`,
      );
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
        return true;
      } finally {
        setProcessing(row.id, false);
      }
    } catch {
      return false;
    }
  }

  /**
   * 切换 is_active 状态
   */
  async function onToggleStatus(newStatus: boolean, row: T): Promise<boolean> {
    return onToggleField('is_active', newStatus, row);
  }

  // ==================== 操作处理器 ====================

  /** 操作按钮点击处理 */
  function handleActionClick(e: OnActionClickParams<T>) {
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
        // 自定义操作
        const action = customActions[e.code];
        if (action) {
          action(e.row);
        }
        break;
      }
    }
  }

  /** 状态切换处理（供列定义使用） */
  function handleToggleStatus(newStatus: boolean, row: T) {
    return onToggleStatus(newStatus, row);
  }

  /**
   * 创建指定字段的 toggle 处理函数（供列定义使用）
   * @param fieldName 字段名，如 'is_active', 'is_visible'
   */
  function createToggleHandler(fieldName: string) {
    return (newStatus: boolean, row: T) =>
      onToggleField(fieldName, newStatus, row);
  }

  // ==================== 表格配置 ====================

  // 构建工具栏配置
  const showExportButton = toolbar.export !== false;
  const toolbarConfig = {
    ...toolbar,
    export: false, // 禁用原生导出，使用自定义导出按钮
  };

  /**
   * 处理表单参数，转换日期范围等特殊字段
   * 日期范围使用 between 操作符: filter[field][between]=start,end
   */
  function processFormValues(formValues: Record<string, any>) {
    const result: Record<string, any> = {};

    for (const [key, value] of Object.entries(formValues)) {
      // 处理日期范围字段: _dateRange_xxx -> filter[xxx][between]=start,end
      if (key.startsWith('_dateRange_') && Array.isArray(value)) {
        const field = key.replace('_dateRange_', '');
        const [startDate, endDate] = value;
        if (startDate && endDate) {
          // 使用 between 操作符，格式: filter[field][between]=start,end
          result[`filter[${field}][between]`] = `${startDate},${endDate}`;
        } else if (startDate) {
          // 只有开始日期，使用 gte
          result[`filter[${field}][gte]`] = startDate;
        } else if (endDate) {
          // 只有结束日期，使用 lte
          result[`filter[${field}][lte]`] = endDate;
        }
      } else if (value !== undefined && value !== null && value !== '') {
        // 过滤空值
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
  };

  // 创建表格
  const [OriginalGrid, _gridApi] = useVbenVxeGrid({
    formOptions: searchSchema
      ? useGridSearchFormOptions(searchSchema)
      : undefined,
    gridOptions,
  });

  // 赋值给闭包引用
  gridApi = _gridApi;

  // 包装 Grid 组件，自动添加导出按钮和导出弹窗
  const Grid = defineComponent({
    name: 'CrudPageGrid',
    inheritAttrs: false,
    setup(_, { attrs, slots }) {
      return () =>
        h('div', { class: 'crud-page-grid h-full' }, [
          h(
            CrudGrid,
            {
              grid: OriginalGrid,
              showExport: showExportButton,
              onExport: openExportModal,
              ...attrs, // 传递所有属性和事件监听器
            },
            slots,
          ),
          // 渲染导出弹窗组件
          h(ExportModal),
        ]);
    },
  });

  return {
    // 组件
    Grid,
    gridApi,
    FormDrawer: FormPopup,
    formApi: formPopupApi,
    ExportModal,

    // CRUD 操作
    onCreate,
    onEdit,
    onDelete,
    onToggleStatus,
    onToggleField,
    onRefresh,
    onReload,

    // 导出
    openExportModal,

    // 处理器
    handleActionClick,
    handleToggleStatus,
    createToggleHandler,
  };
}
