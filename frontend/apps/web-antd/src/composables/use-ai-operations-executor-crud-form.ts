import type { PageOperation } from '#/components/business/ai-runtime/page-operation-types';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

import type { CrudOperationExecutorContext } from './use-ai-operations-executor-types';

import {
  collectRemainingEmptyFields,
  expandDotKeys,
  getFormState,
  isFormOpen,
  sanitizeRemoteSelectOverrides,
  waitForTrackedFormState,
} from './use-ai-operations-state';

function resolveFormDefaults(
  formDefaults?: (() => Record<string, unknown>) | Record<string, unknown>,
): Record<string, unknown> {
  return typeof formDefaults === 'function'
    ? formDefaults()
    : (formDefaults ?? {});
}

export function buildCrudFormOperations(
  context: CrudOperationExecutorContext,
): PageOperation[] {
  const {
    resource,
    loadList,
    list,
    formPopupApi,
    formDefaults,
    hasFormSchema,
    pageKey: optsPageKey,
    rowKeyField,
    formParamsMap,
    createOpParams,
  } = context;

  const operations: PageOperation[] = [];

  if (formPopupApi && hasFormSchema) {
    // ── 5. create_record — Create record (needs formSchema + formPopupApi) / 新建记录 ──
    operations.push({
      name: 'create_record',
      label: $t('shared.pageOperation.createRecord'),
      description: $t('shared.pageOperation.desc.createRecord'),
      readonly: false,
      params:
        Object.keys(createOpParams).length > 0 ? createOpParams : undefined,
      handler: async (params) => {
        if (optsPageKey && isFormOpen(optsPageKey)) {
          const formState = await waitForTrackedFormState(optsPageKey);
          return {
            success: true,
            message: $t('shared.pageOperation.msg.formAlreadyOpen'),
            data: {
              already_open: true,
              current_values: formState.currentValues,
              form_is_open: formState.isOpen,
              remaining_empty_fields: collectRemainingEmptyFields(
                formParamsMap,
                formState.currentValues,
              ),
            },
          };
        }
        // Only accept fields defined in formSchema, ignore unknown fields
        // 只接受 formSchema 中定义的字段，忽略未知字段
        const rawOverrides: Record<string, unknown> = {};
        for (const key of Object.keys(formParamsMap)) {
          if (params[key] !== undefined) rawOverrides[key] = params[key];
        }
        const overrides = sanitizeRemoteSelectOverrides(
          formParamsMap,
          rawOverrides,
        );

        const defaults = resolveFormDefaults(formDefaults);
        formPopupApi
          .setData({
            mode: 'add',
            _resource: resource,
            _defaults: expandDotKeys({ ...defaults, ...overrides }),
            ...(optsPageKey ? { _pageKey: optsPageKey } : {}),
          })
          .open();

        // Wait for Drawer to open and render / 等待 Drawer 打开并渲染完成
        await new Promise<void>((resolve) => setTimeout(resolve, 200));

        const filled = Object.keys(overrides);
        const formState = optsPageKey
          ? await waitForTrackedFormState(optsPageKey)
          : null;
        return {
          success: true,
          message:
            filled.length > 0
              ? $t('shared.pageOperation.msg.createFormOpened', {
                  fields: filled.join(', '),
                })
              : $t('shared.pageOperation.msg.createFormOpenedEmpty'),
          data: {
            current_values: formState?.currentValues ?? {},
            form_is_open: Boolean(formState?.isOpen),
            prefilled_fields: filled,
            remaining_empty_fields: collectRemainingEmptyFields(
              formParamsMap,
              formState?.currentValues ?? {},
              filled,
            ),
            context_diff: {
              form_opened: Boolean(formState?.isOpen),
            },
          },
        };
      },
    });

    // ── 6. edit_record — Edit record (needs formSchema + formPopupApi) / 编辑记录 ──
    const editOpParams: Record<string, unknown> = {
      id: {
        type: 'number',
        description: $t('shared.pageOperation.param.editRecordId'),
        required: true,
      },
      ...createOpParams,
    };

    operations.push({
      name: 'edit_record',
      label: $t('shared.pageOperation.editRecord'),
      description: $t('shared.pageOperation.desc.editRecord'),
      readonly: false,
      params: editOpParams,
      handler: async (params) => {
        if (optsPageKey && isFormOpen(optsPageKey)) {
          const formState = await waitForTrackedFormState(optsPageKey);
          return {
            success: true,
            message: $t('shared.pageOperation.msg.formAlreadyOpen'),
            data: {
              already_open: true,
              current_values: formState.currentValues,
              form_is_open: formState.isOpen,
              remaining_empty_fields: collectRemainingEmptyFields(
                formParamsMap,
                formState.currentValues,
              ),
            },
          };
        }
        const id = params.id;
        if (id === null || id === undefined) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.idRequired'),
          };
        }

        // Find record in current list (try exact match then Number coercion)
        // 在当前列表中查找记录（先精确匹配，再数字转换匹配）
        const rows = list.value as Record<string, unknown>[];
        const record =
          rows.find((r) => r[rowKeyField] === id) ??
          rows.find((r) => String(r[rowKeyField] ?? r.id) === String(id));

        if (!record) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.recordNotFoundInList', {
              id,
            }),
          };
        }

        // Apply overrides (only fields defined in formSchema)
        // 应用覆盖值（只接受 formSchema 中定义的字段）
        const rawOverrides: Record<string, unknown> = {};
        for (const key of Object.keys(formParamsMap)) {
          if (params[key] !== undefined) rawOverrides[key] = params[key];
        }
        const overrides = sanitizeRemoteSelectOverrides(
          formParamsMap,
          rawOverrides,
        );

        const expandedOverrides =
          Object.keys(overrides).length > 0
            ? expandDotKeys(overrides)
            : undefined;

        formPopupApi
          .setData({
            ...record,
            mode: 'edit',
            _resource: resource,
            ...(optsPageKey ? { _pageKey: optsPageKey } : {}),
            ...(expandedOverrides ? { _overrides: expandedOverrides } : {}),
          })
          .open();

        // Wait for Drawer to open and render / 等待 Drawer 打开并渲染完成
        await new Promise<void>((resolve) => setTimeout(resolve, 200));

        const changed = Object.keys(overrides);
        const formState = optsPageKey
          ? await waitForTrackedFormState(optsPageKey)
          : null;
        return {
          success: true,
          message:
            changed.length > 0
              ? $t('shared.pageOperation.msg.editFormOpened', {
                  id,
                  fields: changed.join(', '),
                })
              : $t('shared.pageOperation.msg.editFormOpenedEmpty', { id }),
          data: {
            current_values: formState?.currentValues ?? {},
            form_is_open: Boolean(formState?.isOpen),
            prefilled_fields: changed,
            remaining_empty_fields: collectRemainingEmptyFields(
              formParamsMap,
              formState?.currentValues ?? {},
              changed,
            ),
            context_diff: {
              form_opened: Boolean(formState?.isOpen),
            },
          },
        };
      },
    });

    // ── 5b. delete_record — Delete by ID (same condition as edit_record) / 按 ID 删除记录 ──
    operations.push({
      name: 'delete_record',
      label: $t('shared.pageOperation.deleteRecord'),
      description: $t('shared.pageOperation.desc.deleteRecord'),
      readonly: false,
      params: {
        id: {
          type: 'number',
          description: $t('shared.pageOperation.param.deleteRecordId'),
          required: true,
        },
      },
      handler: async (params) => {
        const id = params.id;
        if (id === null || id === undefined) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.missingIdParam'),
          };
        }
        try {
          await requestClient.delete(`${resource}/${id}`, {
            showSuccessMessage: true,
            showCodeMessage: false,
          });
          await loadList();
          return {
            success: true,
            message: $t('shared.pageOperation.msg.recordDeleted', { id }),
          };
        } catch (error) {
          const msg = error instanceof Error ? error.message : String(error);
          return { success: false, message: msg };
        }
      },
    });
  }

  return operations;
}

export function buildCrudFormStateOperation(
  context: CrudOperationExecutorContext,
): PageOperation | null {
  const { hasFormSchema, pageKey: optsPageKey } = context;
  if (!hasFormSchema || !optsPageKey) {
    return null;
  }

  return {
    name: 'get_form_state',
    label: $t('shared.pageOperation.getFormState'),
    description: $t('shared.pageOperation.desc.getFormState'),
    readonly: true,
    handler: async () => {
      const state = await getFormState(optsPageKey);
      return {
        success: true,
        message: state.isOpen
          ? $t('shared.pageOperation.msg.formIsOpen', { mode: state.mode })
          : $t('shared.pageOperation.msg.formNotOpen'),
        data: {
          isOpen: state.isOpen,
          mode: state.mode,
          currentValues: state.currentValues,
          dirtyFields: state.dirtyFields,
          validationErrors: state.validationErrors,
          fieldDescriptors: state.fieldDescriptors,
        },
      };
    },
  };
}
