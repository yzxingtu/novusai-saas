<script lang="ts" setup>
/**
 * 详情页单字段值渲染 / Detail field value renderer
 * 抽取自 WysiwygDetailView 分组/平铺模式的重复模板
 */

import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';

import { Rate } from 'ant-design-vue';

import { $t } from '#/locales';

import { getComponent } from './field-utils';
import { getPreviewFieldSampleValue } from './preview-builders';

defineOptions({ name: 'DetailFieldValue' });

defineProps<{
  field: Record<string, unknown>;
}>();

defineEmits<{
  (e: 'click'): void;
}>();

/** 获取枚举 mock 展示标签（优先使用配置的 enum_values 第一个项） */
function getEnumSampleLabel(field: Record<string, unknown>): string {
  const ev = field.enum_values as
    | Array<{ label_en?: string; label_zh?: string; value?: string }>
    | undefined;
  if (Array.isArray(ev) && ev.length > 0) {
    const item = ev[0];
    if (item) {
      const locale = String(preferences.app.locale ?? '').toLowerCase();
      const label = locale.startsWith('en') ? item.label_en : item.label_zh;
      return (label ??
        item.value ??
        $t('admin.system.codegen.preview.sampleValue')) as string;
    }
  }
  return $t('admin.system.codegen.preview.sampleValue') as string;
}

/** 主色色块（替代硬编码 #6366f1） */
const PRIMARY_SWATCH = 'var(--primary)';

function isBooleanField(field: Record<string, unknown>): boolean {
  const type = String(field.type || '').toLowerCase();
  return (
    getComponent(field) === 'switch' ||
    type === 'bool' ||
    type.includes('boolean')
  );
}

function getBooleanSample(field: Record<string, unknown>): boolean {
  return Boolean(getPreviewFieldSampleValue(field));
}
</script>

<template>
  <div
    class="-m-0.5 cursor-pointer rounded p-0.5"
    :class="[$attrs.class]"
    role="button"
    tabindex="0"
    @click="$emit('click')"
  >
    <template v-if="getComponent(field) === 'password'">
      <span class="tracking-widest text-muted-foreground">******</span>
    </template>
    <template v-else-if="getComponent(field) === 'ColorPicker'">
      <span
        class="inline-block size-5 rounded border border-border"
        :style="{ backgroundColor: PRIMARY_SWATCH }"
      ></span>
    </template>
    <template v-else-if="getComponent(field) === 'IconPicker'">
      <IconifyIcon icon="lucide:sparkles" class="size-5" />
    </template>
    <template v-else-if="getComponent(field) === 'Slider'">
      <span>50</span>
    </template>
    <template v-else-if="getComponent(field) === 'TimePicker'">
      <span class="text-foreground">14:30:00</span>
    </template>
    <template
      v-else-if="
        getComponent(field) === 'CodeEditor' ||
        String(field.type || '') === 'JSON'
      "
    >
      <code class="text-xs text-muted-foreground">{ ... }</code>
    </template>
    <template
      v-else-if="
        getComponent(field) === 'RichText' ||
        String(field.type || '') === 'RichText'
      "
    >
      <span class="text-xs italic text-muted-foreground">{{
        $t('admin.system.codegen.preview.richTextContent')
      }}</span>
    </template>
    <template v-else-if="isBooleanField(field)">
      <span
        class="rounded px-2 py-0.5 text-xs"
        :class="
          getBooleanSample(field)
            ? 'bg-green-500/10 text-green-600'
            : 'bg-slate-500/10 text-slate-600'
        "
      >
        {{ getBooleanSample(field) ? $t('common.yes') : $t('common.no') }}
      </span>
    </template>
    <template
      v-else-if="
        ['ApiSelect', 'ApiTreeSelect', 'ForeignKey'].includes(
          getComponent(field),
        ) || ['UserSelect', 'DeptSelect'].includes(String(field.type || ''))
      "
    >
      <span class="text-primary">
        {{
          field.relation_table
            ? `${String(field.relation_table).replace(/_/g, ' ')} A (${
                field.relation_display || field.relation_display_field || 'name'
              })`
            : $t('admin.system.codegen.preview.selectRelation')
        }}
      </span>
    </template>
    <template
      v-else-if="
        String(field.type || '')
          .toLowerCase()
          .includes('image')
      "
    >
      <div
        class="flex size-16 items-center justify-center overflow-hidden rounded-lg border border-border/40 bg-muted/20"
      >
        <IconifyIcon icon="lucide:image" class="size-6 text-muted-foreground" />
      </div>
    </template>
    <template
      v-else-if="
        String(field.type || '')
          .toLowerCase()
          .includes('file')
      "
    >
      <span
        role="link"
        tabindex="0"
        class="inline-flex cursor-pointer items-center gap-1 text-xs text-primary hover:underline"
      >
        <IconifyIcon icon="lucide:file" class="size-3.5" />
        {{ $t('admin.system.codegen.preview.sampleFileName') }}
      </span>
    </template>
    <template
      v-else-if="
        String(field.type || '')
          .toLowerCase()
          .includes('date')
      "
    >
      <span class="text-foreground">2024-01-01 12:00:00</span>
    </template>
    <template
      v-else-if="
        String(field.type || '')
          .toLowerCase()
          .includes('enum')
      "
    >
      <span class="rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
        {{ getEnumSampleLabel(field) }}
      </span>
    </template>
    <template v-else-if="getComponent(field) === 'Rate'">
      <Rate disabled :value="3" />
    </template>
    <template v-else>—</template>
  </div>
</template>
