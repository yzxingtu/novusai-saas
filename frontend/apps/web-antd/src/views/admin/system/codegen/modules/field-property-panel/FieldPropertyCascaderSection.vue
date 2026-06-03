<script lang="ts" setup>
import { Input } from 'ant-design-vue';

import { $t } from '#/locales';

import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertyCascaderSection' });

const { onCascaderOptionsChange, selectedField } =
  useFieldPropertyPanelContext();
</script>

<template>
  <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
    <div class="mb-2 text-xs font-medium text-muted-foreground">
      {{ $t('admin.system.codegen.property.cascaderOptions') }}
    </div>
    <div>
      <label class="mb-1 block text-xs">{{
        $t('admin.system.codegen.property.placeholderCascaderOptions')
      }}</label>
      <Input.TextArea
        :value="
          typeof selectedField?.cascader_options === 'string'
            ? selectedField.cascader_options
            : JSON.stringify(selectedField?.cascader_options || [], null, 2)
        "
        :placeholder="
          $t('admin.system.codegen.property.placeholderCascaderOptions')
        "
        :rows="4"
        @update:value="onCascaderOptionsChange"
      />
    </div>
  </section>
</template>
