<script setup lang="ts">
import type { ConfigFormFieldApi, ConfigFormModel } from '../types';

import type { ConfigItemMeta, ConfigValue } from '#/types/config';

import { Input, InputNumber, Select, Switch } from 'ant-design-vue';

import { $t as t } from '#/locales';

import { ConfigHtmlEditor } from '../../config-html-editor';
import { ConfigImagePicker } from '../../config-image-picker';

interface Props {
  config: ConfigItemMeta;
  fieldApi: ConfigFormFieldApi;
  formModel: ConfigFormModel;
  formatJsonValue: (val: ConfigValue | undefined) => string;
  getRuleNumber: (
    cfg: ConfigItemMeta,
    type: 'max_value' | 'min_value',
  ) => number | undefined;
  getSelectOptions: (cfg: ConfigItemMeta) => Array<{
    label: number | string;
    value: number | string;
  }>;
  fallbackRows: number;
  textRows: number;
  withPasswordGenerator?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  withPasswordGenerator: false,
});

const emit = defineEmits<{
  updateJson: [key: string, val: string];
}>();

function updateJson(val: string) {
  emit('updateJson', props.config.key, val);
}
</script>

<template>
  <Input
    v-if="config.value_type === 'string'"
    :value="fieldApi.getStringValue(config.key)"
    :autocomplete="withPasswordGenerator ? 'new-password' : undefined"
    @update:value="(val) => fieldApi.setStringValue(config.key, val)"
  />

  <InputNumber
    v-else-if="config.value_type === 'number'"
    :value="fieldApi.getNumberValue(config.key)"
    :style="{ width: '100%' }"
    :min="getRuleNumber(config, 'min_value')"
    :max="getRuleNumber(config, 'max_value')"
    @update:value="(val) => fieldApi.setNumberValue(config.key, val)"
  />

  <Switch
    v-else-if="config.value_type === 'boolean'"
    :checked="fieldApi.getBooleanValue(config.key)"
    @update:checked="(val) => fieldApi.setBooleanValue(config.key, val)"
  />

  <Select
    v-else-if="config.value_type === 'select'"
    :value="fieldApi.getSelectValue(config.key)"
    :options="getSelectOptions(config)"
    @update:value="(val) => fieldApi.setSelectValue(config.key, val)"
  />

  <Select
    v-else-if="config.value_type === 'multi_select'"
    :value="fieldApi.getMultiSelectValue(config.key)"
    mode="multiple"
    :options="getSelectOptions(config)"
    @update:value="(val) => fieldApi.setMultiSelectValue(config.key, val)"
  />

  <Input.TextArea
    v-else-if="config.value_type === 'text'"
    :value="fieldApi.getStringValue(config.key)"
    :rows="textRows"
    @update:value="(val) => fieldApi.setStringValue(config.key, val)"
  />

  <ConfigHtmlEditor
    v-else-if="config.value_type === 'html'"
    :model-value="fieldApi.getHtmlValue(config.key)"
    @update:model-value="(val) => fieldApi.setHtmlValue(config.key, val)"
  />

  <div
    v-else-if="config.value_type === 'password' && withPasswordGenerator"
    class="flex items-center gap-2"
  >
    <Input.Password
      :value="fieldApi.getStringValue(config.key)"
      autocomplete="new-password"
      :visibility-toggle="fieldApi.getStringValue(config.key) !== '******'"
      class="flex-1"
      @update:value="(val) => fieldApi.setStringValue(config.key, val)"
    />
    <slot
      name="password-extra"
      :set-value="(v: string) => fieldApi.setStringValue(config.key, v)"
    ></slot>
  </div>

  <Input.Password
    v-else-if="config.value_type === 'password'"
    :value="fieldApi.getStringValue(config.key)"
    autocomplete="new-password"
    :visibility-toggle="fieldApi.getStringValue(config.key) !== '******'"
    @update:value="(val) => fieldApi.setStringValue(config.key, val)"
  />

  <div
    v-else-if="config.value_type === 'color'"
    class="flex items-center gap-2"
  >
    <input
      type="color"
      :value="fieldApi.getStringValue(config.key)"
      class="h-8 w-8 cursor-pointer rounded border border-border"
      @input="
        (e) =>
          fieldApi.setStringValue(
            config.key,
            (e.target as HTMLInputElement).value,
          )
      "
    />
    <Input
      :value="fieldApi.getStringValue(config.key)"
      style="width: 120px"
      @update:value="(val) => fieldApi.setStringValue(config.key, val)"
    />
  </div>

  <ConfigImagePicker
    v-else-if="config.value_type === 'image'"
    :model-value="fieldApi.getImageValue(config.key)"
    @update:model-value="(val) => fieldApi.setImageValue(config.key, val)"
  />

  <template
    v-else-if="
      config.value_type === 'json' &&
      config.children &&
      config.children.length > 0
    "
  >
  </template>

  <Input.TextArea
    v-else-if="config.value_type === 'json'"
    :value="formatJsonValue(formModel[config.key])"
    @update:value="(val: string) => updateJson(val)"
    :rows="6"
    :placeholder="t('shared.config.page.json_placeholder')"
  />

  <Input.TextArea
    v-else
    :value="fieldApi.getStringValue(config.key)"
    :rows="fallbackRows"
    @update:value="(val) => fieldApi.setStringValue(config.key, val)"
  />
</template>
