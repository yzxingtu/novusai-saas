<script lang="ts" setup>
/**
 * 添加域名抽屉
 * 使用 useCrudDrawer 实现声明式表单
 */
import type { TenantDomainInfo } from './domains-types';

import { ref } from 'vue';

import { useVbenDrawer, useVbenForm } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import { inputField, textareaField } from '#/adapter/form';
import { adminApi as admin } from '#/api';
import { $t } from '#/locales';

// Emits
const emits = defineEmits<{
  success: [domain: TenantDomainInfo];
}>();

// Current tenant ID / 当前企业 ID
const tenantId = ref<number>();

/** 表单 Schema */
function useFormSchema() {
  return [
    inputField('domain', $t('admin.tenant.domain.domain'), {
      required: true,
      placeholder: $t('admin.tenant.domain.domainPlaceholder'),
    }),
    textareaField('remark', $t('admin.tenant.domain.remark'), {
      placeholder: $t('admin.tenant.domain.remarkPlaceholder'),
      maxLength: 500,
    }),
  ];
}

// Form API
const [FormComponent, formApi] = useVbenForm({
  commonConfig: {
    componentProps: { class: 'w-full' },
    labelWidth: 100,
  },
  schema: useFormSchema(),
  showDefaultActions: false,
});

// Drawer
const [Drawer, drawerApi] = useVbenDrawer({
  onConfirm: onSubmit,
  onOpenChange(isOpen) {
    if (!isOpen) {
      formApi.resetForm();
    }
  },
});

/** 提交表单 */
async function onSubmit() {
  if (!tenantId.value) return;

  const { valid } = await formApi.validate();
  if (!valid) return;

  const values = await formApi.getValues();
  const requestData = {
    domain: values.domain?.trim(),
    remark: values.remark?.trim() || null,
  };

  drawerApi.setState({ loading: true, confirmLoading: true });
  try {
    const result = await admin.createTenantDomainApi(
      tenantId.value,
      requestData,
    );
    message.success($t('admin.tenant.domain.createSuccess'));
    drawerApi.close();
    emits('success', result as TenantDomainInfo);
  } catch {
    // Error handled by request interceptor / 错误由请求拦截器处理
  } finally {
    drawerApi.setState({ loading: false, confirmLoading: false });
  }
}

/** 打开抽屉 */
function open(tid: number) {
  tenantId.value = tid;
  drawerApi.setData({ mode: 'add' }).open();
}

defineExpose({ open });
</script>

<template>
  <Drawer
    :title="$t('admin.tenant.domain.addDomain')"
    :confirm-text="$t('shared.common.confirm')"
  >
    <FormComponent />
  </Drawer>
</template>
