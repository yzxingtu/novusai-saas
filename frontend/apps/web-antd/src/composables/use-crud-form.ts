import type { Ref } from 'vue';

/**
 * 声明式 CRUD 抽屉/弹窗 Composable
 *
 * 配合 useCrudPage 使用，自动处理：
 * - create/update 请求
 * - 表单重置
 * - Schema 切换
 * - 编辑模式数据填充 (自动 camelCase ↔ snake_case)
 *
 * @example
 * ```ts
 * // 标准用法
 * const { Drawer, isEdit } = useCrudDrawer<TenantInfo>({
 *   formApi,
 *   schema: useFormSchema,
 *   // 只需定义字段名，自动处理映射
 *   fields: ['name', 'contact_name', 'contact_phone', 'plan_id'],
 *   onSuccess: () => emits('success'),
 * });
 * ```
 */
import type { FormMode } from '#/adapter/vxe-table';

import { computed, nextTick, ref, unref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';
import { extractFormParams } from './use-ai-operations';
import { formStateTracker } from './use-form-state-tracker';

// ============ 字段映射工具函数 ============

/** snake_case 转 camelCase */
function snakeToCamel(str: string): string {
  return str.replaceAll(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

/**
 * 根据字段列表生成 toFormValues 函数
 * 后端 camelCase -> 表单 snake_case
 */
function createToFormValues<T>(
  fields: string[],
): (data: T) => Record<string, any> {
  return (data: T) => {
    const source = data as Record<string, unknown>;
    const result: Record<string, any> = {};
    for (const field of fields) {
      const camelField = snakeToCamel(field);
      result[field] = source[camelField] ?? source[field];
    }
    return result;
  };
}

/**
 * 根据字段列表生成 transform 函数
 * 表单 snake_case -> API snake_case（空值转 null）
 */
function createTransform(
  fields: string[],
): (values: Record<string, any>) => Record<string, any> {
  return (values: Record<string, any>) => {
    const result: Record<string, any> = {};
    for (const field of fields) {
      const value = values[field];
      // 空字符串转为 null
      result[field] = value === '' || value === undefined ? null : value;
    }
    return result;
  };
}

/**
 * useCrudDrawer 配置选项
 */
export interface UseCrudDrawerOptions<T = any> {
  /** Form API（由 useVbenForm 返回）- 详情页模式可不传 */
  formApi?: {
    getValues: () => Promise<Record<string, any>>;
    resetForm: () => Promise<void>;
    setState: (state: { schema?: any[] }) => void;
    setValues: (values: Record<string, any>) => void;
    validate: () => Promise<{ valid: boolean }>;
  };

  /**
   * Schema 工厂函数
   * @param isEdit 是否编辑模式
   */
  schema?: (isEdit: boolean) => any[];

  /**
   * 字段列表（推荐）
   *
   * 提供字段列表后，自动处理：
   * - 编辑模式：后端 camelCase -> 表单 snake_case
   * - 提交时：表单 snake_case -> API snake_case（空值转 null）
   *
   * @example
   * ```ts
   * fields: ['name', 'contact_name', 'contact_phone', 'plan_id', 'expires_at']
   * ```
   */
  fields?: string[];

  /**
   * API 资源路径（可选）
   *
   * 指定后，openNew/openEdit 会自动使用此路径，无需每次传递 _resource
   */
  apiPath?: (() => string) | Ref<string> | string;

  /**
   * 数据转换函数（表单值 -> API 请求体）
   *
   * 如果提供了 `fields`，则此项可省略
   *
   * @param values 表单原始值
   * @param isEdit 是否编辑模式
   */
  transform?: (
    values: Record<string, any>,
    isEdit: boolean,
  ) => Record<string, any>;

  /**
   * 新建模式的表单默认值
   * 可以是静态对象或工厂函数
   */
  defaults?: (() => Record<string, any>) | Record<string, any>;

  /**
   * 后端数据 -> 表单值（编辑模式）
   *
   * 如果提供了 `fields`，则此项可省略
   *
   * @param data 后端返回的数据
   */
  toFormValues?: (data: T) => Record<string, any>;

  /** 成功回调 */
  onSuccess?: () => void;

  /**
   * 保存后回调（可选）
   *
   * 在 API 请求成功后、onSuccess 之前调用。
   * 可用于保存关联数据（如技能脚本）。
   *
   * @param response API 响应数据
   * @param formValues 表单原始值
   * @param isEdit 是否编辑模式
   */
  afterSave?: (
    response: any,
    formValues: Record<string, any>,
    isEdit: boolean,
  ) => Promise<void> | void;

  /** 打开时额外操作（如加载远程数据） */
  onOpen?: () => Promise<void> | void;

  /** 打开后额外操作（如更新下拉选项） */
  afterOpen?: (formApi: any, isEdit: boolean) => Promise<void> | void;

  /**
   * 详情 API（可选）
   *
   * 提供后，编辑模式会调用此 API 获取完整数据，而不是使用列表传递的行数据
   */
  detailApi?: (id: number | string) => Promise<T>;

  /**
   * 主键字段名
   * @default 'id'
   */
  idField?: string;

  /**
   * AI page key (enables form state tracking for AI operations)
   * AI 页面标识（启用表单状态追踪供 AI 操作使用）
   */
  aiPageKey?: string;
}

/**
 * 一体化 CRUD 抽屉
 * 整合 useVbenDrawer + useCrudForm，简化表单组件
 */
export function useCrudDrawer<T = any>(options: UseCrudDrawerOptions<T>) {
  const {
    formApi,
    schema,
    fields,
    transform: customTransform,
    defaults,
    toFormValues: customToFormValues,
    onSuccess,
    afterSave,
    onOpen,
    afterOpen,
    apiPath,
    detailApi,
    idField = 'id',
    aiPageKey: staticAiPageKey,
  } = options;

  let aiPageKey = staticAiPageKey;

  // 如果提供了 fields，自动生成 transform 和 toFormValues
  const transform =
    customTransform ?? (fields ? createTransform(fields) : (v: any) => v);
  const toFormValues =
    customToFormValues ?? (fields ? createToFormValues<T>(fields) : undefined);

  const mode = ref<FormMode>('add');
  const recordId = ref<number | string>();
  const resource = ref<string>('');
  const rowData = ref<T>();
  /** 详情数据（通过 detailApi 获取） */
  const detailData = ref<T>();

  const isEdit = computed(() => mode.value === 'edit');

  // 防抖状态
  const isSubmitting = ref(false);

  const [Drawer, drawerApi] = useVbenDrawer({
    async onConfirm() {
      // 防抖：如果正在提交中，直接返回
      if (isSubmitting.value) return;

      if (!formApi) return;

      const { valid } = await formApi.validate();
      if (!valid) return;

      const values = await formApi.getValues();
      const requestData = transform(values, isEdit.value);

      isSubmitting.value = true;
      drawerApi.lock();

      try {
        const response = await (isEdit.value && recordId.value
          ? requestClient.put(
              `${resource.value}/${recordId.value}`,
              requestData,
              {
                showSuccessMessage: true,
                successMessage: $t('ui.actionMessage.updateSuccess'),
              },
            )
          : requestClient.post(resource.value, requestData, {
              showSuccessMessage: true,
              successMessage: $t('ui.actionMessage.createSuccess'),
            }));
        if (afterSave) {
          await afterSave(response, values, isEdit.value);
        }
        if (aiPageKey) formStateTracker.close(aiPageKey);
        await onSuccess?.();
        drawerApi.close();
      } catch {
        drawerApi.unlock();
      } finally {
        isSubmitting.value = false;
      }
    },

    async onOpenChange(isOpen) {
      if (!isOpen) {
        if (aiPageKey) formStateTracker.close(aiPageKey);
        return;
      }

      // 从 drawerApi 获取数据
      const data = drawerApi.getData() as
        | (T & {
            [key: string]: any;
            _defaults?: Record<string, any>;
            _resource?: string;
            id?: number | string;
            mode?: FormMode;
          })
        | undefined;
      mode.value = data?.mode ?? 'add';
      recordId.value = data?.[idField];

      if (!aiPageKey && data?._aiPageKey) {
        aiPageKey = data._aiPageKey as string;
      }
      {
        const p = unref(apiPath) as (() => string) | string | undefined;
        const resolved = typeof p === 'function' ? p() : p;
        resource.value = data?._resource ?? resolved ?? '';
      }
      rowData.value = data as T;

      // 重置表单
      await formApi?.resetForm();

      // 执行 onOpen（如加载远程数据）
      await onOpen?.();

      // 更新 schema
      if (schema && formApi) {
        formApi.setState({ schema: schema(isEdit.value) });
      }
      await nextTick();

      // 执行 afterOpen（如更新下拉选项）
      await afterOpen?.(formApi, isEdit.value);

      // 填充表单数据
      if (isEdit.value || mode.value === 'view') {
        // 编辑或查看模式：优先调用详情 API 获取完整数据
        let fetchedData: T | undefined = data as T;
        if (detailApi && recordId.value) {
          try {
            drawerApi.setState({ loading: true });
            fetchedData = await detailApi(recordId.value);
            detailData.value = fetchedData;
          } catch {
            // 详情加载失败，回退到行数据
            fetchedData = data as T;
          } finally {
            drawerApi.setState({ loading: false });
          }
        }
        if (toFormValues && fetchedData && formApi) {
          formApi.setValues(toFormValues(fetchedData));
        }
      } else {
        // 新建模式：优先使用 _defaults（从 useCrudPage 传入），否则使用本地 defaults 配置
        const defaultValues =
          data?._defaults ??
          (typeof defaults === 'function' ? defaults() : defaults);
        if (defaultValues && formApi) {
          formApi.setValues(defaultValues);
        }
      }

      // Register form state for AI tracking / 注册表单状态供 AI 追踪
      if (aiPageKey && formApi) {
        const fieldDescriptors = schema
          ? extractFormParams(schema(isEdit.value))
          : {};
        let initialValues: Record<string, unknown> = {};
        try {
          initialValues = await formApi.getValues();
        } catch {
          // Form may not be fully ready
        }
        formStateTracker.open(aiPageKey, {
          mode: mode.value as 'add' | 'edit' | 'view',
          formApi: formApi as any,
          fieldDescriptors,
          initialValues,
        });
      }
    },
  });

  /**
   * 打开新建模式
   * @param extraData 额外传递给 Drawer 的数据
   */
  function openNew(extraData?: Record<string, any>) {
    const p = unref(apiPath) as (() => string) | string | undefined;
    const path = typeof p === 'function' ? p() : p;
    drawerApi
      .setData({
        mode: 'add',
        ...(path ? { _resource: path } : {}),
        ...extraData,
      })
      .open();
  }

  /**
   * 打开编辑模式
   * @param record 要编辑的记录
   * @param extraData 额外传递给 Drawer 的数据
   */
  function openEdit(record: Partial<T>, extraData?: Record<string, any>) {
    const p = unref(apiPath) as (() => string) | string | undefined;
    const path = typeof p === 'function' ? p() : p;
    drawerApi
      .setData({
        ...record,
        mode: 'edit',
        ...(path ? { _resource: path } : {}),
        ...extraData,
      })
      .open();
  }

  return {
    Drawer,
    drawerApi,
    isEdit,
    mode,
    recordId,
    resource,
    rowData,
    detailData,
    openNew,
    openEdit,
  };
}
