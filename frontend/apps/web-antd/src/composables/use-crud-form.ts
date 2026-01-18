/**
 * 声明式 CRUD 抽屉/弹窗 Composable
 *
 * 配合 useCrudPage 使用，自动处理：
 * - create/update 请求
 * - 表单重置
 * - Schema 切换
 * - 编辑模式数据填充
 *
 * @example
 * ```ts
 * const { Drawer, drawerApi, isEdit } = useCrudDrawer<AdminInfo>({
 *   formApi,
 *   schema: useFormSchema,
 *   transform: (values, isEdit) => ({ ... }),
 *   toFormValues: (data) => ({ ... }),
 *   onSuccess: () => emits('success'),
 * });
 * ```
 */
import type { FormMode } from '#/adapter/vxe-table';

import { computed, nextTick, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

/**
 * useCrudDrawer 配置选项
 */
export interface UseCrudDrawerOptions<T = any> {
  /** Form API（由 useVbenForm 返回） */
  formApi: {
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
  schema: (isEdit: boolean) => any[];

  /**
   * 数据转换函数（表单值 -> API 请求体）
   * @param values 表单原始值
   * @param isEdit 是否编辑模式
   */
  transform: (
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
   * @param data 后端返回的数据
   */
  toFormValues?: (data: T) => Record<string, any>;

  /** 成功回调 */
  onSuccess?: () => void;

  /** 打开时额外操作（如加载远程数据） */
  onOpen?: () => Promise<void> | void;

  /** 打开后额外操作（如更新下拉选项） */
  afterOpen?: (formApi: any, isEdit: boolean) => Promise<void> | void;
}

/**
 * 一体化 CRUD 抽屉
 * 整合 useVbenDrawer + useCrudForm，进一步简化表单组件
 */
export function useCrudDrawer<T = any>(options: UseCrudDrawerOptions<T>) {
  const {
    formApi,
    schema,
    transform,
    defaults,
    toFormValues,
    onSuccess,
    onOpen,
    afterOpen,
  } = options;

  const mode = ref<FormMode>('add');
  const recordId = ref<number | string>();
  const resource = ref<string>('');
  const rowData = ref<T>();

  const isEdit = computed(() => mode.value === 'edit');

  // 防抖状态
  const isSubmitting = ref(false);

  const [Drawer, drawerApi] = useVbenDrawer({
    async onConfirm() {
      // 防抖：如果正在提交中，直接返回
      if (isSubmitting.value) return;

      const { valid } = await formApi.validate();
      if (!valid) return;

      const values = await formApi.getValues();
      const requestData = transform(values, isEdit.value);

      isSubmitting.value = true;
      drawerApi.lock();

      try {
        await (isEdit.value && recordId.value
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
        await onSuccess?.();
        drawerApi.close();
      } catch {
        drawerApi.unlock();
      } finally {
        isSubmitting.value = false;
      }
    },

    async onOpenChange(isOpen) {
      if (!isOpen) return;

      // 从 drawerApi 获取数据
      const data = drawerApi.getData() as
        | (T & {
            _defaults?: Record<string, any>;
            _resource?: string;
            id?: number | string;
            mode?: FormMode;
          })
        | undefined;
      mode.value = data?.mode ?? 'add';
      recordId.value = data?.id;
      resource.value = data?._resource ?? '';
      rowData.value = data as T;

      // 重置表单
      await formApi.resetForm();

      // 执行 onOpen（如加载远程数据）
      await onOpen?.();

      // 更新 schema
      formApi.setState({ schema: schema(isEdit.value) });
      await nextTick();

      // 执行 afterOpen（如更新下拉选项）
      await afterOpen?.(formApi, isEdit.value);

      // 填充表单数据
      if (isEdit.value) {
        // 编辑模式：填充后端数据
        if (toFormValues && data) {
          formApi.setValues(toFormValues(data as T));
        }
      } else {
        // 新建模式：优先使用 _defaults（从 useCrudPage 传入），否则使用本地 defaults 配置
        const defaultValues =
          data?._defaults ??
          (typeof defaults === 'function' ? defaults() : defaults);
        if (defaultValues) {
          formApi.setValues(defaultValues);
        }
      }
    },
  });

  return {
    Drawer,
    drawerApi,
    isEdit,
    mode,
    recordId,
    resource,
    rowData,
  };
}
