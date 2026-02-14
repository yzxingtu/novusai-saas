<script setup lang="ts">
/**
 * I18nPreview — 多语种 i18n JSON 并排显示 + inline 编辑
 *
 * 功能: 并排显示 zh-CN / en-US / 其他语种的翻译 JSON,
 *       支持 inline 编辑微调, 支持动态添加语种
 */
import { computed, reactive, ref, watch } from 'vue';

import {
  Button,
  Card,
  Empty,
  Input,
  Select,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
}>();

const emit = defineEmits<{
  (e: 'update:i18n', locale: string, data: Record<string, string>): void;
}>();

// ============================================================
// Locale management
// ============================================================

const AVAILABLE_LOCALES = [
  { label: '日本語 (ja-JP)', value: 'ja-JP' },
  { label: '한국어 (ko-KR)', value: 'ko-KR' },
  { label: 'Français (fr-FR)', value: 'fr-FR' },
  { label: 'Deutsch (de-DE)', value: 'de-DE' },
  { label: 'Español (es-ES)', value: 'es-ES' },
  { label: 'Português (pt-BR)', value: 'pt-BR' },
  { label: 'Русский (ru-RU)', value: 'ru-RU' },
  { label: 'العربية (ar-SA)', value: 'ar-SA' },
];

const activeLocales = ref<string[]>(['zh-CN', 'en-US']);
const newLocale = ref<string | undefined>(undefined);

function addLocale() {
  if (newLocale.value && !activeLocales.value.includes(newLocale.value)) {
    activeLocales.value.push(newLocale.value);
    newLocale.value = undefined;
  }
}

function removeLocale(locale: string) {
  if (locale === 'zh-CN' || locale === 'en-US') return;
  activeLocales.value = activeLocales.value.filter((l) => l !== locale);
}

const addableLocales = computed(() =>
  AVAILABLE_LOCALES.filter((l) => !activeLocales.value.includes(l.value)),
);

// ============================================================
// Generate i18n keys from config
// ============================================================

const i18nKeys = computed(() => {
  const keys: string[] = [];
  const module = props.config.module || 'module';

  keys.push(`${module}.title`);
  keys.push(`${module}.createTitle`);
  keys.push(`${module}.editTitle`);

  for (const field of props.config.fields) {
    keys.push(`${module}.field.${field.name}`);
  }

  for (const enumDef of props.config.enums) {
    for (const val of enumDef.values) {
      keys.push(`${module}.enum.${enumDef.name}.${val.value}`);
    }
  }

  keys.push(`${module}.search.placeholder`);
  keys.push(`${module}.message.createSuccess`);
  keys.push(`${module}.message.updateSuccess`);
  keys.push(`${module}.message.deleteSuccess`);
  keys.push(`${module}.message.deleteConfirm`);

  return keys;
});

// ============================================================
// i18n data per locale
// ============================================================

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const i18nData = reactive<Record<string, Record<string, string>>>({});

function getZhValue(key: string): string {
  const module = props.config.module || 'module';
  const parts = key.replace(`${module}.`, '').split('.');

  if (parts[0] === 'title') return props.config.display_name || props.config.module || '';
  if (parts[0] === 'createTitle') return `${$t(`${T}.formPreview.createTitle`, { name: props.config.display_name || '' })}`;
  if (parts[0] === 'editTitle') return `${$t(`${T}.formPreview.editTitle`, { name: props.config.display_name || '' })}`;

  if (parts[0] === 'field' && parts[1]) {
    const field = props.config.fields.find((f) => f.name === parts[1]);
    return field?.label_zh || parts[1] || '';
  }

  if (parts[0] === 'enum' && parts[1] && parts[2]) {
    const enumDef = props.config.enums.find((e) => e.name === parts[1]);
    const val = enumDef?.values.find((v) => v.value === parts[2]);
    return val?.label_zh || parts[2] || '';
  }

  if (parts[0] === 'search') return '搜索';
  if (parts[0] === 'message') {
    const msgs: Record<string, string> = {
      createSuccess: '创建成功',
      updateSuccess: '更新成功',
      deleteSuccess: '删除成功',
      deleteConfirm: '确认删除？',
    };
    return msgs[parts[1] || ''] || '';
  }

  return key;
}

function getEnValue(key: string): string {
  const module = props.config.module || 'module';
  const parts = key.replace(`${module}.`, '').split('.');

  if (parts[0] === 'title') return props.config.display_name_en || props.config.module || '';
  if (parts[0] === 'createTitle') return `Create ${props.config.display_name_en || ''}`;
  if (parts[0] === 'editTitle') return `Edit ${props.config.display_name_en || ''}`;

  if (parts[0] === 'field' && parts[1]) {
    const field = props.config.fields.find((f) => f.name === parts[1]);
    return field?.label_en || parts[1] || '';
  }

  if (parts[0] === 'enum' && parts[1] && parts[2]) {
    const enumDef = props.config.enums.find((e) => e.name === parts[1]);
    const val = enumDef?.values.find((v) => v.value === parts[2]);
    return val?.label_en || parts[2] || '';
  }

  if (parts[0] === 'search') return 'Search';
  if (parts[0] === 'message') {
    const msgs: Record<string, string> = {
      createSuccess: 'Created successfully',
      updateSuccess: 'Updated successfully',
      deleteSuccess: 'Deleted successfully',
      deleteConfirm: 'Are you sure to delete?',
    };
    return msgs[parts[1] || ''] || '';
  }

  return key;
}

function getLocaleValue(locale: string, key: string): string {
  if (locale === 'zh-CN') return i18nData[locale]?.[key] ?? getZhValue(key);
  if (locale === 'en-US') return i18nData[locale]?.[key] ?? getEnValue(key);
  return i18nData[locale]?.[key] ?? '';
}

function setLocaleValue(locale: string, key: string, value: string) {
  if (!i18nData[locale]) {
    i18nData[locale] = {};
  }
  i18nData[locale]![key] = value;
  emit('update:i18n', locale, { ...i18nData[locale] });
}

// Initialize zh-CN and en-US data from config
watch(
  () => [props.config.fields, props.config.enums],
  () => {
    for (const key of i18nKeys.value) {
      if (!i18nData['zh-CN']?.[key]) {
        setLocaleValue('zh-CN', key, getZhValue(key));
      }
      if (!i18nData['en-US']?.[key]) {
        setLocaleValue('en-US', key, getEnValue(key));
      }
    }
  },
  { immediate: true, deep: true },
);
</script>

<template>
  <div class="space-y-4">
    <!-- Locale tabs -->
    <div class="flex items-center gap-2">
      <Tag
        v-for="locale in activeLocales"
        :key="locale"
        :closable="locale !== 'zh-CN' && locale !== 'en-US'"
        color="blue"
        @close="removeLocale(locale)"
      >
        {{ locale }}
      </Tag>
      <div class="flex items-center gap-1">
        <Select
          v-model:value="newLocale"
          :options="addableLocales"
          :placeholder="'+ ' + $t(`${T}.steps.preview`)"
          size="small"
          style="width: 160px"
        />
        <Button :disabled="!newLocale" size="small" type="link" @click="addLocale">
          <span class="icon-[lucide--plus] size-3.5" />
        </Button>
      </div>
    </div>

    <!-- Empty state -->
    <Empty v-if="i18nKeys.length === 0" description="No i18n keys" class="py-8" />

    <!-- Side-by-side table -->
    <Card v-else size="small">
      <div class="overflow-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b">
              <th class="text-muted-foreground px-2 py-1.5 text-left font-medium" style="min-width: 180px">
                Key
              </th>
              <th
                v-for="locale in activeLocales"
                :key="locale"
                class="text-muted-foreground px-2 py-1.5 text-left font-medium"
                style="min-width: 200px"
              >
                {{ locale }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="key in i18nKeys"
              :key="key"
              class="hover:bg-accent/30 border-b transition-colors"
            >
              <td class="text-muted-foreground px-2 py-1 font-mono text-xs">
                {{ key }}
              </td>
              <td
                v-for="locale in activeLocales"
                :key="`${key}-${locale}`"
                class="px-1 py-0.5"
              >
                <Input
                  :value="getLocaleValue(locale, key)"
                  size="small"
                  class="border-transparent hover:border-primary/30 focus:border-primary"
                  @change="(e: Event) => setLocaleValue(locale, key, (e.target as HTMLInputElement).value)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>
