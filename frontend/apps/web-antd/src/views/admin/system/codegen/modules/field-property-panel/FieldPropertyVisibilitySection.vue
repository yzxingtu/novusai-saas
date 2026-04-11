<script lang="ts" setup>
import { Switch } from 'ant-design-vue';

import { $t } from '#/locales';

import { useFieldPropertyPanelContext } from './context';

defineOptions({ name: 'FieldPropertyVisibilitySection' });

const { asBoolean, selectedField, updateField } =
  useFieldPropertyPanelContext();
</script>

<template>
  <div class="border-b border-border/60 px-3 py-2.5">
    <div class="grid grid-cols-2 gap-1.5">
      <div
        class="flex items-center justify-between gap-2 rounded-xl border border-border/70 bg-muted/15 px-2.5 py-1.5"
      >
        <span class="text-xs text-muted-foreground">
          {{ $t('admin.system.codegen.property.required') }}
        </span>
        <Switch
          size="small"
          :checked="asBoolean(selectedField?.required)"
          @update:checked="
            (value) => updateField({ required: asBoolean(value) })
          "
        />
      </div>
      <div
        class="flex items-center justify-between gap-2 rounded-xl border border-border/70 bg-muted/15 px-2.5 py-1.5"
      >
        <span class="text-xs text-muted-foreground">
          {{ $t('admin.system.codegen.property.nullable') }}
        </span>
        <Switch
          size="small"
          :checked="asBoolean(selectedField?.nullable)"
          @update:checked="
            (value) => updateField({ nullable: asBoolean(value) })
          "
        />
      </div>
      <div
        class="flex items-center justify-between gap-2 rounded-xl border border-border/70 bg-muted/15 px-2.5 py-1.5"
      >
        <span class="text-xs text-muted-foreground">
          {{ $t('admin.system.codegen.property.listVisible') }}
        </span>
        <Switch
          size="small"
          :checked="selectedField?.list_visible !== false"
          @update:checked="
            (value) => updateField({ list_visible: asBoolean(value) })
          "
        />
      </div>
      <div
        class="flex items-center justify-between gap-2 rounded-xl border border-border/70 bg-muted/15 px-2.5 py-1.5"
      >
        <span class="text-xs text-muted-foreground">
          {{ $t('admin.system.codegen.property.filterable') }}
        </span>
        <Switch
          size="small"
          :checked="asBoolean(selectedField?.filterable)"
          @update:checked="
            (value) => updateField({ filterable: asBoolean(value) })
          "
        />
      </div>
    </div>
  </div>
</template>
