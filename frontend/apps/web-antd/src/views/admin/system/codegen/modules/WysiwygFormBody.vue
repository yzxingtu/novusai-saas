<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Cascader,
  DatePicker,
  Empty,
  Input,
  InputNumber,
  Rate,
  Select,
  Slider,
  Switch,
  TimePicker,
  Tooltip,
  TreeSelect,
} from 'ant-design-vue';

import { ApiSelect } from '#/components/business/api-select';
import CronPicker from '#/components/business/cron-picker/CronPicker.vue';
import { IconPicker } from '#/components/business/icon-picker';
import RichTextEditor from '#/components/business/rich-text-editor/RichTextEditor.vue';
import { $t } from '#/locales';

import { useWysiwygFormContext } from './wysiwyg-form-context';

defineOptions({ name: 'WysiwygFormBody' });

const {
  asBoolean,
  asNumberOrUndefined,
  features,
  formItemsWithDividers,
  getBooleanValue,
  getCascaderValue,
  getDateRangeValue,
  getDateValue,
  getDictMockOptions,
  getEnumOptions,
  getFieldLabel,
  getFieldPlaceholder,
  getMockCascaderOptions,
  getMockRelationOptions,
  getMockTreeOptions,
  getMultipleAwareSelectValue,
  getNumberValue,
  getRelationApi,
  getRelationPlaceholder,
  getRichTextAi,
  getRichTextValue,
  getScalarSelectValue,
  getSelectValue,
  getStringValue,
  getTreeValue,
  handleCancel,
  handleSubmit,
  hasFormFields,
  isDatetimeType,
  isFieldSelected,
  isMultiple,
  onFieldClick,
  onNativeColorInput,
  richTextDefaultDoc,
  setFormValue,
} = useWysiwygFormContext();
</script>

<template>
  <div v-if="hasFormFields" class="bg-muted/10 p-5">
    <div
      class="mx-auto max-w-5xl overflow-hidden rounded-[24px] border border-border/70 bg-background shadow-sm"
    >
      <div class="border-b border-border/50 px-5 py-4">
        <div
          class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
        >
          <IconifyIcon icon="lucide:mouse-pointer" class="size-4" />
          <span>{{ $t('admin.system.codegen.builder.previewFieldHint') }}</span>
        </div>
      </div>

      <div
        class="p-5"
        :class="
          features.formColumns.value === 2
            ? 'grid grid-cols-1 gap-4 xl:grid-cols-2'
            : 'flex flex-col gap-4'
        "
      >
        <template
          v-for="(f, i) in formItemsWithDividers"
          :key="(f.__key as string) || f.name || `d-${i}`"
        >
          <template v-if="f.divider || f.type === '__divider__'">
            <div
              class="rounded-2xl border border-dashed border-border/70 bg-muted/15 px-4 py-3"
              :class="[features.formColumns.value === 2 && 'xl:col-span-2']"
            >
              <div
                class="text-[11px] uppercase tracking-[0.16em] text-muted-foreground"
              >
                {{ $t('admin.system.codegen.palette.divider') }}
              </div>
              <div class="mt-1 text-sm font-medium text-foreground">
                {{ f.divider_title || f.title || '' }}
              </div>
            </div>
          </template>
          <div
            v-else
            class="flex flex-col gap-2 rounded-[20px] border border-border/70 bg-background px-4 py-4 transition-colors"
            :class="[isFieldSelected(f) && 'border-primary ring-2 ring-primary/15']"
            @mousedown="onFieldClick(f)"
          >
            <label class="text-xs text-muted-foreground">
              <span v-if="f.required" class="mr-0.5 text-destructive">*</span>
              <Tooltip v-if="f.comment" :title="f.comment">
                <span>{{
                  getFieldLabel(f) || $t('admin.system.codegen.property.unnamed')
                }}</span>
              </Tooltip>
              <span v-else>{{
                getFieldLabel(f) || $t('admin.system.codegen.property.unnamed')
              }}</span>
            </label>
            <Input
              v-if="(f._comp as string) === 'input'"
              :value="getStringValue(f)"
              :maxlength="(f.max_length as number) ?? undefined"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.pleaseInput',
                )
              "
              @update:value="(value) => setFormValue(f, value)"
            />
            <Input
              v-else-if="(f._comp as string) === 'password'"
              :value="getStringValue(f)"
              type="password"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.pleaseInput',
                )
              "
              @update:value="(value) => setFormValue(f, value)"
            />
            <Input.TextArea
              v-else-if="(f._comp as string) === 'textarea'"
              :value="getStringValue(f)"
              :maxlength="(f.max_length as number) ?? undefined"
              :rows="2"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.pleaseInput',
                )
              "
              @update:value="(value) => setFormValue(f, value)"
            />
            <InputNumber
              v-else-if="(f._comp as string) === 'number'"
              :value="getNumberValue(f)"
              :min="(f.min_value as number) ?? undefined"
              :max="(f.max_value as number) ?? undefined"
              class="w-full"
              @update:value="
                (value) => setFormValue(f, asNumberOrUndefined(value))
              "
            />
            <Select
              v-else-if="
                ['select', 'radio', 'checkbox'].includes(
                  (f._comp as string) || '',
                )
              "
              :value="getSelectValue(f)"
              :options="getEnumOptions(f)"
              :mode="(f._comp as string) === 'checkbox' ? 'multiple' : undefined"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.pleaseSelect',
                )
              "
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <div
              v-else-if="(f._comp as string) === 'switch'"
              class="flex w-fit items-center"
            >
              <Switch
                :checked="getBooleanValue(f)"
                @update:checked="(value) => setFormValue(f, asBoolean(value))"
              />
            </div>
            <DatePicker
              v-else-if="(f._comp as string) === 'date' && isDatetimeType(f)"
              :value="getDateValue(f)"
              show-time
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.datePlaceholder',
                )
              "
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <DatePicker
              v-else-if="(f._comp as string) === 'date'"
              :value="getDateValue(f)"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.datePlaceholder',
                )
              "
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <div
              v-else-if="(f._comp as string) === 'ImageUpload'"
              class="flex w-full flex-col gap-1.5"
            >
              <div
                class="flex min-h-[80px] items-center justify-center gap-2 rounded border border-dashed border-border bg-muted/30"
                :class="isMultiple(f) ? 'flex-row flex-wrap' : ''"
              >
                <div class="flex flex-col items-center justify-center gap-1 py-4">
                  <IconifyIcon
                    icon="lucide:image-plus"
                    class="size-8 text-muted-foreground"
                  />
                  <span class="text-xs text-muted-foreground">
                    {{
                      isMultiple(f)
                        ? $t('admin.system.codegen.preview.uploadImageMulti')
                        : $t('admin.system.codegen.preview.uploadImage')
                    }}
                  </span>
                  <span
                    v-if="f.max_count"
                    class="text-xs text-muted-foreground"
                  >
                    {{
                      $t('admin.system.codegen.preview.maxCountHint', {
                        count: f.max_count,
                      })
                    }}
                  </span>
                </div>
                <div
                  v-if="isMultiple(f)"
                  class="flex size-16 shrink-0 items-center justify-center rounded border border-dashed border-border bg-muted/20"
                >
                  <IconifyIcon
                    icon="lucide:image-plus"
                    class="size-5 text-muted-foreground"
                  />
                </div>
              </div>
            </div>
            <div
              v-else-if="(f._comp as string) === 'FilePicker'"
              class="flex w-full flex-col gap-1.5"
            >
              <div
                class="flex min-h-[64px] items-center justify-center gap-2 rounded border border-dashed border-border bg-muted/30"
                :class="isMultiple(f) ? 'flex-row flex-wrap' : ''"
              >
                <div class="flex flex-col items-center justify-center gap-1 py-3">
                  <IconifyIcon
                    icon="lucide:file-plus"
                    class="size-6 text-muted-foreground"
                  />
                  <span class="text-xs text-muted-foreground">
                    {{
                      isMultiple(f)
                        ? $t('admin.system.codegen.preview.uploadFileMulti')
                        : $t('admin.system.codegen.preview.uploadFile')
                    }}
                  </span>
                  <span
                    v-if="f.max_count"
                    class="text-xs text-muted-foreground"
                  >
                    {{
                      $t('admin.system.codegen.preview.maxCountHint', {
                        count: f.max_count,
                      })
                    }}
                  </span>
                </div>
                <div
                  v-if="isMultiple(f)"
                  class="flex size-12 shrink-0 items-center justify-center rounded border border-dashed border-border bg-muted/20"
                >
                  <IconifyIcon
                    icon="lucide:file"
                    class="size-4 text-muted-foreground"
                  />
                </div>
              </div>
            </div>
            <div
              v-else-if="
                (f._comp as string) === 'RichText' ||
                String(f.type || '').trim() === 'RichText'
              "
              class="w-full"
            >
              <RichTextEditor
                :model-value="getRichTextValue(f)"
                :default-value="richTextDefaultDoc"
                :placeholder="getFieldPlaceholder(f, 'common.editorPlaceholder')"
                mode="compact"
                :toolbar="true"
                :ai="getRichTextAi(f)"
                :upload="false"
                :editable="true"
                :min-height="120"
                class="rounded border border-border"
                @update:model-value="(value) => setFormValue(f, value)"
              />
            </div>
            <ApiSelect
              v-else-if="
                (f._comp as string) === 'ApiSelect' &&
                f.relation_table &&
                !isMultiple(f)
              "
              :key="`rel-${f.relation_table}-${f.relation_display || f.relation_display_field || 'name'}`"
              :value="getScalarSelectValue(f)"
              :api="getRelationApi(f)"
              :placeholder="
                f.placeholder && String(f.placeholder).trim()
                  ? String(f.placeholder).trim()
                  : getRelationPlaceholder(f)
              "
              result-field="items"
              label-field="label"
              value-field="value"
              search-param-name="search"
              :page-size="200"
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <Select
              v-else-if="(f._comp as string) === 'ApiSelect'"
              :value="getMultipleAwareSelectValue(f)"
              :options="getMockRelationOptions(f)"
              :placeholder="
                f.placeholder && String(f.placeholder).trim()
                  ? String(f.placeholder).trim()
                  : getRelationPlaceholder(f)
              "
              :mode="isMultiple(f) ? 'multiple' : undefined"
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <TreeSelect
              v-else-if="
                ['ApiTreeSelect', 'TreeSelect'].includes(
                  (f._comp as string) || '',
                )
              "
              :value="getTreeValue(f)"
              :tree-data="getMockTreeOptions(f)"
              :placeholder="
                f.placeholder && String(f.placeholder).trim()
                  ? String(f.placeholder).trim()
                  : getRelationPlaceholder(f)
              "
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <Cascader
              v-else-if="(f._comp as string) === 'Cascader'"
              :value="getCascaderValue(f)"
              :options="getMockCascaderOptions(f)"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.pleaseSelect',
                )
              "
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <TimePicker
              v-else-if="(f._comp as string) === 'TimePicker'"
              :value="getDateValue(f)"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.timePlaceholder',
                )
              "
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <div
              v-else-if="(f._comp as string) === 'ColorPicker'"
              class="flex items-center gap-2"
            >
              <div
                class="relative size-8 shrink-0 cursor-pointer overflow-hidden rounded border border-border"
              >
                <input
                  :value="getStringValue(f)"
                  type="color"
                  class="absolute inset-0 size-full cursor-pointer opacity-0"
                  @input="(event) => onNativeColorInput(f, event)"
                />
                <div
                  class="absolute inset-0"
                  :style="{ backgroundColor: getStringValue(f) || '#6366f1' }"
                ></div>
              </div>
              <Input
                :value="getStringValue(f)"
                class="flex-1 font-mono text-xs"
                :placeholder="
                  f.placeholder && String(f.placeholder).trim()
                    ? String(f.placeholder).trim()
                    : '#6366f1'
                "
                @update:value="(value) => setFormValue(f, value)"
              />
            </div>
            <div
              v-else-if="(f._comp as string) === 'IconPicker'"
              class="min-w-0 flex-1"
            >
              <IconPicker
                :value="getStringValue(f)"
                :placeholder="
                  f.placeholder && String(f.placeholder).trim()
                    ? String(f.placeholder).trim()
                    : 'lucide:sparkles'
                "
                @update:value="(value) => setFormValue(f, value)"
              />
            </div>
            <Rate
              v-else-if="(f._comp as string) === 'Rate'"
              :value="getNumberValue(f)"
              @update:value="
                (value) => setFormValue(f, asNumberOrUndefined(value))
              "
            />
            <Slider
              v-else-if="(f._comp as string) === 'Slider'"
              :value="getNumberValue(f)"
              @update:value="
                (value) => setFormValue(f, asNumberOrUndefined(value))
              "
            />
            <Select
              v-else-if="(f._comp as string) === 'DictSelect'"
              :value="getScalarSelectValue(f)"
              :options="getDictMockOptions(f)"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.dictSelectPlaceholder',
                )
              "
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <div
              v-else-if="(f._comp as string) === 'CodeEditor'"
              class="h-20 w-full rounded border border-border bg-muted/20 font-mono text-xs"
            ></div>
            <CronPicker
              v-else-if="(f._comp as string) === 'CronPicker'"
              :value="getStringValue(f)"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.cronPlaceholder',
                )
              "
              @update:value="(value) => setFormValue(f, value)"
            />
            <DatePicker.RangePicker
              v-else-if="(f._comp as string) === 'RangePicker'"
              :value="getDateRangeValue(f)"
              :placeholder="[
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.rangePlaceholder',
                ),
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.rangePlaceholder',
                ),
              ]"
              class="w-full"
              @update:value="(value) => setFormValue(f, value)"
            />
            <div
              v-else-if="(f._comp as string) === 'Upload'"
              class="flex h-16 w-full items-center justify-center gap-2 rounded border border-dashed border-border bg-muted/30"
            >
              <IconifyIcon
                icon="lucide:upload"
                class="size-6 text-muted-foreground"
              />
              <span class="text-xs text-muted-foreground">
                {{ $t('admin.system.codegen.preview.uploadFile') }}
              </span>
            </div>
            <Input
              v-else
              :value="getStringValue(f)"
              :maxlength="(f.max_length as number) ?? undefined"
              :placeholder="
                getFieldPlaceholder(
                  f,
                  'admin.system.codegen.preview.pleaseInput',
                )
              "
              @update:value="(value) => setFormValue(f, value)"
            />
            <span v-if="f.help_text" class="mt-0.5 text-xs text-muted-foreground"
              >{{ f.help_text }}</span
            >
          </div>
        </template>
      </div>

      <div
        class="flex justify-end gap-2 border-t border-border/50 bg-muted/10 px-5 py-4"
      >
        <Button size="small" @click="handleCancel">
          {{ $t('common.cancel') }}
        </Button>
        <Button size="small" type="primary" @click="handleSubmit">
          {{ $t('common.confirm') }}
        </Button>
      </div>
    </div>
  </div>

  <div v-else class="bg-muted/10 py-12">
    <Empty :image="Empty.PRESENTED_IMAGE_SIMPLE">
      <template #description>
        <p class="mb-1">{{ $t('admin.system.codegen.wysiwyg.emptyHint') }}</p>
        <p class="text-xs text-muted-foreground">
          {{ $t('admin.system.codegen.wysiwyg.dragHint') }}
        </p>
      </template>
    </Empty>
  </div>
</template>
