<script lang="ts" setup>
/**
 * 添加域名抽屉；使用 useVbenForm 声明式表单。
 * Add domain drawer; declarative form via useVbenForm.
 */
import type { TenantDomainInfo } from './domains-types';

import { useVbenDrawer, useVbenForm } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import { inputField, textareaField } from '#/adapter/form';
import { createTenantDomainApi } from '#/api/tenant/domain';
import { $t } from '#/locales';

// Emits / 组件事件
const emits = defineEmits<{
  success: [domain: TenantDomainInfo];
}>();

interface DomainCreateDefaults {
  domain?: string;
  remark?: string;
}

/** 表单 Schema / Form schema */
function useFormSchema() {
  return [
    inputField('domain', $t('tenant.system.domain.domain'), {
      required: true,
      placeholder: $t('tenant.system.domain.placeholder.inputDomain'),
    }),
    textareaField('remark', $t('tenant.system.domain.remark'), {
      placeholder: $t('tenant.system.domain.placeholder.inputRemark'),
      maxLength: 500,
    }),
  ];
}

// Form API / 表单 API
const [FormComponent, formApi] = useVbenForm({
  commonConfig: {
    componentProps: { class: 'w-full' },
    labelWidth: 100,
  },
  schema: useFormSchema(),
  showDefaultActions: false,
});

// Drawer / 抽屉
const [Drawer, drawerApi] = useVbenDrawer({
  onConfirm: onSubmit,
  onOpenChange(isOpen) {
    if (!isOpen) {
      formApi.resetForm();
    }
  },
});

/** 提交表单 / Submit form */
async function onSubmit() {
  const { valid } = await formApi.validate();
  if (!valid) return;

  const values = await formApi.getValues();
  const requestData = {
    domain: values.domain?.trim(),
    remark: values.remark?.trim() || undefined,
  };

  drawerApi.setState({ loading: true, confirmLoading: true });
  try {
    const result = await createTenantDomainApi(requestData);
    message.success($t('tenant.system.domain.messages.addSuccess'));
    drawerApi.close();
    emits('success', result as TenantDomainInfo);
  } catch {
    // Error handled by request interceptor / 错误由请求拦截器处理
    drawerApi.setState({ loading: false, confirmLoading: false });
  } finally {
    drawerApi.setState({ loading: false, confirmLoading: false });
  }
}

/** 打开抽屉 / Open drawer */
async function open(defaults?: DomainCreateDefaults) {
  await formApi.resetForm();
  if (defaults && Object.keys(defaults).length > 0) {
    await formApi.setValues(defaults);
  }
  drawerApi.setData({ mode: 'add' }).open();
}

defineExpose({ open });
</script>

<template>
  <Drawer
    :title="$t('tenant.system.domain.add')"
    :confirm-text="$t('common.confirm')"
  >
    <FormComponent />
  </Drawer>
</template>
