<script lang="ts" setup>
import { Input } from 'ant-design-vue';

import { $t } from '#/locales';

import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertyBasicSection' });

const { onNameChange, selectedField, strVal, updateField } =
  useFieldPropertyPanelContext();
</script>

<template>
  <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
    <div class="mb-2 text-xs font-medium text-muted-foreground">
      {{ $t('admin.system.codegen.property.basic') }}
    </div>
    <div class="flex flex-col gap-3">
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.fieldName')
        }}</label>
        <Input
          :value="strVal(selectedField?.name)"
          :placeholder="
            $t('admin.system.codegen.property.placeholderSnakeCase')
          "
          @update:value="onNameChange"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.displayNameZh')
        }}</label>
        <Input
          :value="strVal(selectedField?.display_name)"
          :placeholder="$t('admin.system.codegen.property.placeholderZh')"
          @update:value="updateField({ display_name: $event })"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.displayNameEn')
        }}</label>
        <Input
          :value="strVal(selectedField?.display_name_en)"
          :placeholder="$t('admin.system.codegen.property.placeholderEn')"
          @update:value="updateField({ display_name_en: $event })"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.comment')
        }}</label>
        <Input
          :value="strVal(selectedField?.comment)"
          :placeholder="
            $t('admin.system.codegen.property.placeholderDbComment')
          "
          @update:value="updateField({ comment: $event })"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.placeholder')
        }}</label>
        <Input
          :value="strVal(selectedField?.placeholder)"
          :placeholder="$t('admin.system.codegen.property.placeholderOptional')"
          @update:value="updateField({ placeholder: $event })"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs">{{
          $t('admin.system.codegen.property.helpText')
        }}</label>
        <Input
          :value="strVal(selectedField?.help_text)"
          :placeholder="$t('admin.system.codegen.property.placeholderOptional')"
          @update:value="updateField({ help_text: $event })"
        />
      </div>
    </div>
  </section>
</template>
