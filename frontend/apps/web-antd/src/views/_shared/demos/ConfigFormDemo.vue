<script setup lang="ts">
import type { ConfigItemMeta } from '#/types/config';

import { ref } from 'vue';

import { Button } from 'ant-design-vue';

import { ConfigForm } from '#/components';
import { $t as t } from '#/locales';

const form = ref();

const configs = ref<ConfigItemMeta[]>([
  {
    key: 'site_name',
    name_key: 'config.platform.site_name',
    value_type: 'string',
    value: 'NovusAI',
    is_required: true,
  },
  {
    key: 'password_min_length',
    name_key: 'config.platform.password_min_length',
    value_type: 'number',
    default_value: 8,
    validation_rules: [
      { type: 'min_value', value: 6, message_key: 'validation.min_value' },
    ],
  },
  {
    key: 'maintenance_mode',
    name_key: 'config.platform.maintenance_mode',
    value_type: 'boolean',
    default_value: false,
  },
  {
    key: 'password_complexity',
    name_key: 'config.platform.password_complexity',
    value_type: 'select',
    default_value: 'medium',
    options: [
      { value: 'low', label_key: 'config.platform.password_complexity.low' },
      {
        value: 'medium',
        label_key: 'config.platform.password_complexity.medium',
      },
      { value: 'high', label_key: 'config.platform.password_complexity.high' },
    ],
  },
  {
    key: 'tenant_primary_color',
    name_key: 'config.tenant.tenant_primary_color',
    value_type: 'color',
    default_value: '#1890ff',
  },
  {
    key: 'email_smtp_password',
    name_key: 'config.platform.email_smtp_password',
    value_type: 'password',
    is_encrypted: true,
  },
  {
    key: 'site_logo',
    name_key: 'config.platform.site_logo',
    value_type: 'image',
    default_value: '',
  },
]);

async function onSubmit() {
  await form.value?.validate();
  // const payload = form.value?.prepareSubmitData();
}
</script>

<template>
  <div style="max-width: 860px">
    <ConfigForm ref="form" :configs="configs" />
    <div style="margin-top: 16px">
      <Button type="primary" @click="onSubmit">
        {{ t('shared.common.save') }}
      </Button>
    </div>
  </div>
</template>
