import type { PageOperation } from '#/components/business/ai-runtime/page-operation-types';
import type { VbenFormSchema } from '#/core/adapter/form/setup';

import { $t } from '#/locales';

import { resolveFormOptionsFieldName } from './form-option-param-utils';
import {
  requireOpenForm,
  requireOpenFormApi,
} from './use-ai-operations-confirmation';
import {
  ensureRemoteOptionsWithTimeout,
  resolveRemoteOptions,
} from './use-ai-operations-remote-options';
import {
  buildFieldParamSchema,
  extractFormParams,
} from './use-ai-operations-schema';
import {
  buildFillFormFeedback,
  expandDotKeys,
  getFormState,
} from './use-ai-operations-state';

export function buildFormOperations(options: {
  pageKey: string;
  formSchema: (isEdit?: boolean) => VbenFormSchema[];
  resource: string;
}): PageOperation[] {
  const { pageKey, formSchema, resource } = options;

  const rawFormSchema = formSchema(false);
  const formParamsMap = extractFormParams(rawFormSchema);

  const createOpParams: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(formParamsMap)) {
    createOpParams[key] = buildFieldParamSchema(entry, {
      includeDefaultValue: false,
      includeRequired: false,
    });
  }

  let _remoteResolved = false;
  let _remoteResolvePromise: null | Promise<void> = null;
  async function ensureRemoteOptions(): Promise<void> {
    if (_remoteResolved || rawFormSchema.length === 0) return;
    if (_remoteResolvePromise) {
      await _remoteResolvePromise;
      return;
    }
    _remoteResolvePromise = (async () => {
      const remoteOpts = await resolveRemoteOptions(rawFormSchema, resource);
      for (const [field, options] of remoteOpts) {
        const existing = formParamsMap[field];
        if (existing && !existing.options) {
          existing.options = options;
        }
      }
      _remoteResolved = true;
    })();
    try {
      await _remoteResolvePromise;
    } finally {
      _remoteResolvePromise = null;
    }
  }
  if (
    rawFormSchema.some(
      (s) =>
        s.component === 'ApiSelect' ||
        s.component === 'ApiTreeSelect' ||
        s.component === 'IdentityRemoteSelect',
    )
  ) {
    ensureRemoteOptions();
  }

  const operations: PageOperation[] = [
    // get_form_state / 获取表单状态
    {
      name: 'get_form_state',
      label: $t('shared.pageOperation.getFormState'),
      description: $t('shared.pageOperation.desc.getFormState'),
      readonly: true,
      handler: async () => {
        const state = await getFormState(pageKey);
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
    },

    // fill_form / 填充表单
    {
      name: 'fill_form',
      label: $t('shared.pageOperation.fillForm'),
      description: $t('shared.pageOperation.desc.fillForm'),
      readonly: false,
      params:
        Object.keys(createOpParams).length > 0 ? createOpParams : undefined,
      handler: async (params) => {
        const access = requireOpenFormApi(pageKey);
        if (!access.ok) {
          return access.result;
        }

        const validFields: Record<string, unknown> = {};
        const skippedFields: string[] = [];
        for (const [key, value] of Object.entries(params)) {
          if (formParamsMap[key]) {
            validFields[key] = value;
          } else {
            skippedFields.push(key);
          }
        }

        if (Object.keys(validFields).length === 0) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.noValidFields', {
              fields: Object.keys(formParamsMap).join(', '),
            }),
          };
        }

        try {
          access.formApi.setValues(expandDotKeys(validFields));
          await new Promise<void>((r) => setTimeout(r, 100));
        } catch {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.setFormValuesFailed'),
          };
        }

        const filledKeys = Object.keys(validFields);
        const { feedback, mismatchCount } = await buildFillFormFeedback(
          access.formApi,
          validFields,
        );
        const skippedInfo =
          skippedFields.length > 0
            ? `. ${$t('shared.pageOperation.msg.skippedUnknown', { fields: skippedFields.join(', ') })}`
            : '';
        return {
          success: true,
          message:
            (mismatchCount > 0
              ? $t('shared.pageOperation.msg.fillFormPartial', {
                  count: filledKeys.length,
                  mismatch: mismatchCount,
                })
              : $t('shared.pageOperation.msg.fillFormResult', {
                  count: filledKeys.length,
                })) + skippedInfo,
          data: {
            filled: filledKeys,
            skipped: skippedFields,
            field_feedback: feedback,
          },
        };
      },
    },
    // validate_form / 校验表单
    {
      name: 'validate_form',
      label: $t('shared.pageOperation.validateForm'),
      description: $t('shared.pageOperation.desc.validateForm'),
      readonly: true,
      handler: async () => {
        const access = requireOpenFormApi(pageKey);
        if (!access.ok) {
          return access.result;
        }
        try {
          const { valid } = await access.formApi.validate();
          return {
            success: true,
            message: valid
              ? $t('shared.pageOperation.msg.allFieldsValid')
              : $t('shared.pageOperation.msg.formHasValidationErrors'),
            data: { valid },
          };
        } catch {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.validationFailed'),
          };
        }
      },
    },
    // submit_form / 提交表单
    {
      name: 'submit_form',
      label: $t('shared.pageOperation.submitForm'),
      description: $t('shared.pageOperation.desc.submitForm'),
      readonly: false,
      handler: async () => {
        const access = requireOpenFormApi(pageKey);
        if (!access.ok) {
          return access.result;
        }
        const validResult = await access.formApi.validate();
        const valid =
          validResult && (validResult as { valid?: boolean }).valid !== false;
        const errors = (validResult as { errors?: Record<string, unknown> })
          ?.errors;
        if (!valid && errors && Object.keys(errors).length > 0) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.validationFailedMsg'),
            data: { errors },
          };
        }
        if (access.formApi.submitForm) {
          try {
            await access.formApi.submitForm();
            return {
              success: true,
              message: $t('shared.pageOperation.msg.formSubmittedSuccess'),
            };
          } catch (error) {
            const msg = error instanceof Error ? error.message : String(error);
            return { success: false, message: msg };
          }
        }
        return {
          success: false,
          message: $t('shared.pageOperation.msg.formApiNotAvailable'),
        };
      },
    },
  ];

  // get_form_options / 获取远程下拉选项
  const remoteFields = Object.entries(formParamsMap)
    .filter(([_, desc]) => desc.optionsSource === 'remote')
    .map(([key]) => key);

  if (remoteFields.length > 0) {
    operations.push({
      name: 'get_form_options',
      label: $t('shared.pageOperation.getFormOptions'),
      description: $t('shared.pageOperation.desc.getFormOptions', {
        fields: remoteFields.join(', '),
      }),
      readonly: true,
      params: {
        field_name: {
          type: 'string',
          description: $t('shared.pageOperation.param.exactFieldName', {
            fields: remoteFields.join(', '),
          }),
          required: true,
        },
      },
      handler: async (params) => {
        const openCheck = requireOpenForm(pageKey);
        if (!openCheck.ok) {
          return openCheck.result;
        }
        const fieldName = resolveFormOptionsFieldName(params);
        if (!fieldName || !formParamsMap[fieldName]) {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.unknownField', {
              field: fieldName,
              available: remoteFields.join(', '),
            }),
          };
        }

        const status = await ensureRemoteOptionsWithTimeout(ensureRemoteOptions);
        if (status === 'timeout') {
          return {
            success: false,
            message: $t('shared.pageOperation.msg.optionsLoadTimeout', {
              field: fieldName,
            }),
          };
        }
        const desc = formParamsMap[fieldName];
        if (desc?.options && desc.options.length > 0) {
          return {
            success: true,
            message: $t('shared.pageOperation.msg.foundOptions', {
              field: fieldName,
              count: desc.options.length,
            }),
            data: { field: fieldName, options: desc.options },
          };
        }

        return {
          success: true,
          message: $t('shared.pageOperation.msg.noOptionsLoaded', {
            field: fieldName,
          }),
          data: { field: fieldName, options: [] },
        };
      },
    });
  }

  return operations;
}
