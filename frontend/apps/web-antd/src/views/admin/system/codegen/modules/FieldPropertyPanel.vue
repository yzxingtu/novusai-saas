<script lang="ts" setup>
/**
 * 字段属性面板 / Field Property Panel
 *
 * 右侧属性面板，选中字段时显示
 */
import { provide } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Checkbox,
  Input,
  InputNumber,
  Select,
  Switch,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';

import EnumValuesEditor from './EnumValuesEditor.vue';
import { fieldPropertyPanelContextKey } from './field-property-panel/context';
import FieldPropertyFormSection from './field-property-panel/FieldPropertyFormSection.vue';
import FieldPropertyRelationSection from './field-property-panel/FieldPropertyRelationSection.vue';
import { useFieldPropertyPanel } from './field-property-panel/use-field-property-panel';

defineOptions({ name: 'FieldPropertyPanel' });

const panel = useFieldPropertyPanel();
provide(fieldPropertyPanelContextKey, panel);

const {
  applyRecommendedConfig,
  asBoolean,
  asNumberOrUndefined,
  asString,
  enumRenderOptions,
  getEnumValues,
  isDivider,
  onCascaderOptionsChange,
  onNameChange,
  onTypeChange,
  recommendMessage,
  selectedField,
  selectedFieldForm,
  selectedFieldIcon,
  selectedFieldLabel,
  selectedFieldType,
  selectedFormComponent,
  showInferHint,
  showRecommend,
  showSelectRelationConfig,
  showTreeRelationConfig,
  showUserRelationConfig,
  strVal,
  summaryTags,
  typeOptions,
  updateField,
} = panel;
</script>

<template>
  <div
    v-if="!selectedField"
    class="flex flex-1 flex-col items-center justify-center gap-3 p-5 text-center text-muted-foreground"
  >
    <div
      class="flex size-12 items-center justify-center rounded-2xl bg-muted/25"
    >
      <IconifyIcon icon="lucide:sliders-horizontal" class="size-6" />
    </div>
    <span class="text-sm font-medium text-foreground">{{
      $t('admin.system.codegen.property.title')
    }}</span>
    <span class="max-w-xs text-xs leading-6">{{
      $t('admin.system.codegen.property.selectFieldHint')
    }}</span>
  </div>
  <div
    v-else-if="isDivider"
    class="flex flex-1 flex-col gap-3 overflow-y-auto p-3"
  >
    <div
      class="rounded-[16px] border border-dashed border-border/70 bg-muted/15 p-3"
    >
      <div
        class="text-[11px] uppercase tracking-[0.16em] text-muted-foreground"
      >
        {{ $t('admin.system.codegen.palette.divider') }}
      </div>
      <label class="mb-1 mt-3 block text-xs font-medium text-foreground">
        {{ $t('admin.system.codegen.property.displayNameZh') }}
      </label>
      <Input
        :value="strVal(selectedField.divider_title || selectedField.title)"
        :placeholder="
          $t('admin.system.codegen.palette.dividerTitlePlaceholder')
        "
        @update:value="updateField({ divider_title: $event, title: $event })"
      />
    </div>
  </div>
  <div v-else class="flex flex-1 flex-col overflow-hidden">
    <div class="border-b border-border/70 px-3 py-3">
      <div class="flex items-start justify-between gap-3">
        <div class="flex min-w-0 items-start gap-3">
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted/20 ring-1 ring-border/70"
          >
            <IconifyIcon
              :icon="selectedFieldIcon"
              class="size-4.5 text-foreground"
            />
          </div>
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold text-foreground">
              {{
                selectedFieldLabel ||
                $t('admin.system.codegen.property.unnamed')
              }}
            </div>
            <div class="mt-1 truncate font-mono text-xs text-muted-foreground">
              {{ selectedField.name || 'field' }}
            </div>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <Tag
                v-for="tag in summaryTags"
                :key="tag"
                class="!mr-0 !rounded-full"
              >
                {{ tag }}
              </Tag>
              <Tag
                v-if="selectedField._auto_detected"
                color="success"
                class="!mr-0 !rounded-full"
              >
                {{ $t('admin.system.codegen.field.autoDetected') }}
              </Tag>
            </div>
          </div>
        </div>
        <Button
          v-if="showRecommend"
          size="small"
          type="primary"
          ghost
          @click="applyRecommendedConfig"
        >
          {{ $t('admin.system.codegen.property.applyRecommend') }}
        </Button>
      </div>

      <Alert
        v-if="showInferHint"
        type="success"
        show-icon
        class="mt-3 !py-1 text-xs"
        :message="$t('admin.system.codegen.property.inferHint')"
      />
      <Alert
        v-else-if="
          showRecommend &&
          typeof recommendMessage === 'string' &&
          recommendMessage.trim()
        "
        type="info"
        show-icon
        class="mt-3 !py-1 text-xs"
        :message="recommendMessage"
      />
    </div>

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
            :checked="asBoolean(selectedField.required)"
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
            :checked="asBoolean(selectedField.nullable)"
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
            :checked="selectedField.list_visible !== false"
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
            :checked="asBoolean(selectedField.filterable)"
            @update:checked="
              (value) => updateField({ filterable: asBoolean(value) })
            "
          />
        </div>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-3">
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
              :value="strVal(selectedField.name)"
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
              :value="strVal(selectedField.display_name)"
              :placeholder="$t('admin.system.codegen.property.placeholderZh')"
              @update:value="updateField({ display_name: $event })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.displayNameEn')
            }}</label>
            <Input
              :value="strVal(selectedField.display_name_en)"
              :placeholder="$t('admin.system.codegen.property.placeholderEn')"
              @update:value="updateField({ display_name_en: $event })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.comment')
            }}</label>
            <Input
              :value="strVal(selectedField.comment)"
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
              :value="strVal(selectedField.placeholder)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderOptional')
              "
              @update:value="updateField({ placeholder: $event })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.helpText')
            }}</label>
            <Input
              :value="strVal(selectedField.help_text)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderOptional')
              "
              @update:value="updateField({ help_text: $event })"
            />
          </div>
        </div>
      </section>

      <div class="h-2"></div>

      <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
        <div class="mb-2 text-xs font-medium text-muted-foreground">
          {{ $t('admin.system.codegen.property.database') }}
        </div>
        <div class="flex flex-col gap-3">
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.type')
            }}</label>
            <Select
              :value="selectedFieldType"
              class="w-full"
              :options="typeOptions"
              :placeholder="
                $t('admin.system.codegen.property.placeholderSelectType')
              "
              @change="onTypeChange"
            />
          </div>
          <div v-if="selectedFieldType === 'String'">
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.length')
            }}</label>
            <InputNumber
              :value="asNumberOrUndefined(selectedField.max_length)"
              :min="1"
              class="w-full"
              :placeholder="
                $t('admin.system.codegen.property.placeholderExampleLength')
              "
              @update:value="
                (value) =>
                  updateField({ max_length: asNumberOrUndefined(value) })
              "
            />
          </div>
          <template v-if="selectedFieldType === 'Decimal'">
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.precision')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.precision) ?? 10"
                :min="1"
                :max="65"
                class="w-full"
                @update:value="
                  (value) =>
                    updateField({ precision: asNumberOrUndefined(value) })
                "
              />
            </div>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.scale')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.scale) ?? 2"
                :min="0"
                :max="30"
                class="w-full"
                @update:value="
                  (value) => updateField({ scale: asNumberOrUndefined(value) })
                "
              />
            </div>
          </template>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.defaultValue')
            }}</label>
            <Input
              :value="strVal(selectedField.default)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderOptional')
              "
              @update:value="updateField({ default: $event })"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs">{{
              $t('admin.system.codegen.property.dbDefault')
            }}</label>
            <Input
              :value="strVal(selectedField.db_default)"
              :placeholder="
                $t('admin.system.codegen.property.placeholderDbDefault')
              "
              @update:value="updateField({ db_default: $event })"
            />
          </div>
          <div class="flex flex-wrap gap-4">
            <Checkbox
              :checked="asBoolean(selectedField.unique)"
              @update:checked="
                (value) => updateField({ unique: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.unique') }}
            </Checkbox>
            <Checkbox
              :checked="asBoolean(selectedField.index)"
              @update:checked="
                (value) => updateField({ index: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.index') }}
            </Checkbox>
          </div>
        </div>
      </section>

      <div class="h-2"></div>

      <FieldPropertyFormSection />

      <template v-if="selectedFieldType === 'Enum'">
        <div class="h-2"></div>
        <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
          <div class="mb-2 text-xs font-medium text-muted-foreground">
            {{ $t('admin.system.codegen.property.enum') }}
          </div>
          <div class="flex flex-col gap-3">
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.dictCode')
              }}</label>
              <Input
                :value="strVal(selectedField.dict_code)"
                :placeholder="
                  $t('admin.system.codegen.property.placeholderDictCode')
                "
                allow-clear
                @update:value="updateField({ dict_code: $event || undefined })"
              />
              <div class="mt-1 text-xs text-muted-foreground">
                {{ $t('admin.system.codegen.property.dictCodeHelp') }}
              </div>
            </div>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.enumRender')
              }}</label>
              <Select
                :value="
                  asString(selectedFieldForm.enumRender) ||
                  asString(selectedField.enum_render) ||
                  'select'
                "
                class="w-full"
                :options="enumRenderOptions"
                @change="
                  (value) =>
                    updateField({
                      form: {
                        ...selectedFieldForm,
                        enumRender: asString(value),
                      },
                      enum_render: asString(value),
                    })
                "
              />
            </div>
            <EnumValuesEditor
              :model-value="getEnumValues(selectedField)"
              @update:model-value="updateField({ enum_values: $event })"
            />
          </div>
        </section>
      </template>

      <template v-if="showTreeRelationConfig">
        <div class="h-2"></div>
        <FieldPropertyRelationSection mode="tree" />
      </template>

      <template v-if="showSelectRelationConfig">
        <div class="h-2"></div>
        <FieldPropertyRelationSection mode="select" />
      </template>

      <template v-if="showUserRelationConfig">
        <div class="h-2"></div>
        <FieldPropertyRelationSection mode="user" />
      </template>

      <template v-if="selectedFieldType === 'Cascader'">
        <div class="h-2"></div>
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
                typeof selectedField.cascader_options === 'string'
                  ? selectedField.cascader_options
                  : JSON.stringify(
                      selectedField.cascader_options || [],
                      null,
                      2,
                    )
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

      <template
        v-if="
          [
            'Image',
            'ImageUpload',
            'File',
            'FilePicker',
            'Images',
            'Files',
          ].includes(selectedFieldType) ||
          selectedFormComponent === 'ImageUpload' ||
          selectedFormComponent === 'FilePicker'
        "
      >
        <div class="h-2"></div>
        <section class="rounded-xl border border-border/70 bg-muted/10 p-3">
          <div class="mb-2 text-xs font-medium text-muted-foreground">
            {{ $t('admin.system.codegen.property.upload') }}
          </div>
          <div class="flex flex-col gap-3">
            <Checkbox
              :checked="asBoolean(selectedField.multiple)"
              @update:checked="
                (value) => updateField({ multiple: asBoolean(value) })
              "
            >
              {{ $t('admin.system.codegen.property.multiple') }}
            </Checkbox>
            <div>
              <label class="mb-1 block text-xs">{{
                $t('admin.system.codegen.property.maxCount')
              }}</label>
              <InputNumber
                :value="asNumberOrUndefined(selectedField.max_count) ?? 9"
                :min="1"
                class="w-full"
                @update:value="
                  (value) =>
                    updateField({ max_count: asNumberOrUndefined(value) })
                "
              />
            </div>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>
