<script lang="ts" setup>
import type {
  AnnouncementFieldType,
  AnnouncementFormField,
  AnnouncementFormOption,
  AnnouncementPayload,
  AnnouncementPriority,
} from '#/types/announcement';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Collapse,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Switch,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { createAnnouncementFormField } from '#/types/announcement';

defineOptions({ name: 'AnnouncementFormEditor' });

const props = defineProps<{
  locked?: boolean;
  modelValue: AnnouncementPayload;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: AnnouncementPayload];
}>();

const form = ref<AnnouncementPayload>({
  content: '',
  form_schema: [],
  priority: 'normal',
  require_response: false,
  sort_order: 0,
  title: '',
});

const priorityOptions = computed(() =>
  (['low', 'normal', 'high', 'urgent'] as AnnouncementPriority[]).map(
    (value) => ({
      label: $t(`common.announcement.priority.${value}`),
      value,
    }),
  ),
);

const fieldTypeOptions = computed(() =>
  (['consent', 'text', 'radio', 'checkbox'] as AnnouncementFieldType[]).map(
    (value) => ({
      label: $t(`common.announcement.fieldTypes.${value}`),
      value,
    }),
  ),
);

watch(
  () => props.modelValue,
  (value) => {
    form.value = {
      content: value.content ?? '',
      form_schema: value.form_schema ?? [],
      priority: value.priority ?? 'normal',
      require_response: Boolean(value.require_response),
      sort_order: value.sort_order ?? 0,
      title: value.title ?? '',
    };
  },
  { deep: true, immediate: true },
);

function commit(next: AnnouncementPayload) {
  form.value = next;
  emit('update:modelValue', next);
}

function patchForm(patch: Partial<AnnouncementPayload>) {
  commit({
    ...form.value,
    ...patch,
  });
}

function patchField(index: number, patch: Partial<AnnouncementFormField>) {
  const fields = [...form.value.form_schema];
  const current = fields[index];
  if (!current) {
    return;
  }
  fields[index] = {
    ...current,
    ...patch,
  };
  patchForm({ form_schema: fields });
}

function addField(type: AnnouncementFieldType) {
  const fields = [...form.value.form_schema];
  fields.push(createAnnouncementFormField(type, fields.length));
  patchForm({ form_schema: fields, require_response: true });
}

function updatePriority(value: unknown) {
  patchForm({ priority: String(value) as AnnouncementPriority });
}

function removeField(index: number) {
  const fields = form.value.form_schema.filter(
    (_field, fieldIndex) => fieldIndex !== index,
  );
  patchForm({ form_schema: fields });
}

function moveField(index: number, offset: -1 | 1) {
  const nextIndex = index + offset;
  if (nextIndex < 0 || nextIndex >= form.value.form_schema.length) {
    return;
  }
  const fields = [...form.value.form_schema];
  const current = fields[index];
  const target = fields[nextIndex];
  if (!current || !target) {
    return;
  }
  fields[index] = target;
  fields[nextIndex] = current;
  patchForm({ form_schema: fields });
}

function normalizeOptions(
  field: AnnouncementFormField,
): AnnouncementFormOption[] {
  return field.options ?? [];
}

function addOption(index: number) {
  const field = form.value.form_schema[index];
  if (!field) {
    return;
  }
  const options = normalizeOptions(field);
  patchField(index, {
    options: [
      ...options,
      {
        label: '',
        value: `option_${options.length + 1}`,
      },
    ],
  });
}

function removeOption(index: number, optionIndex: number) {
  const field = form.value.form_schema[index];
  if (!field) {
    return;
  }
  patchField(index, {
    options: normalizeOptions(field).filter(
      (_option, currentIndex) => currentIndex !== optionIndex,
    ),
  });
}

function patchOption(
  index: number,
  optionIndex: number,
  patch: Partial<AnnouncementFormOption>,
) {
  const field = form.value.form_schema[index];
  if (!field) {
    return;
  }
  const options = [...normalizeOptions(field)];
  const option = options[optionIndex];
  if (!option) {
    return;
  }
  options[optionIndex] = {
    ...option,
    ...patch,
  };
  patchField(index, { options });
}
</script>

<template>
  <Form layout="vertical" class="announcement-form-editor">
    <div class="grid gap-4 md:grid-cols-2">
      <Form.Item :label="$t('common.announcement.title')" required>
        <Input
          :value="form.title"
          :placeholder="$t('common.announcement.titlePlaceholder')"
          @update:value="(value) => patchForm({ title: value })"
        />
      </Form.Item>

      <Form.Item :label="$t('common.announcement.priorityLabel')">
        <Select
          :value="form.priority"
          :options="priorityOptions"
          @update:value="updatePriority"
        />
      </Form.Item>
    </div>

    <Form.Item :label="$t('common.announcement.content')">
      <Input.TextArea
        :value="form.content ?? ''"
        :disabled="locked"
        :placeholder="$t('common.announcement.contentPlaceholder')"
        :rows="6"
        @update:value="(value) => patchForm({ content: value })"
      />
    </Form.Item>

    <div class="grid gap-4 md:grid-cols-2">
      <Form.Item :label="$t('common.announcement.requireResponse')">
        <Switch
          :checked="form.require_response"
          :disabled="locked"
          @update:checked="
            (value) => patchForm({ require_response: Boolean(value) })
          "
        />
      </Form.Item>

      <Form.Item :label="$t('common.announcement.sortOrder')">
        <InputNumber
          :value="form.sort_order"
          class="w-full"
          @update:value="
            (value) => patchForm({ sort_order: Number(value ?? 0) })
          "
        />
      </Form.Item>
    </div>

    <div v-if="form.require_response" class="space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="text-sm font-medium">
          {{ $t('common.announcement.formFields') }}
        </span>
        <Space wrap>
          <Button
            v-for="item in fieldTypeOptions"
            :key="item.value"
            :disabled="locked"
            size="small"
            @click="addField(item.value)"
          >
            <template #icon>
              <IconifyIcon icon="lucide:plus" class="size-3.5" />
            </template>
            {{ item.label }}
          </Button>
        </Space>
      </div>

      <Collapse
        v-if="form.form_schema.length > 0"
        :bordered="false"
        class="bg-transparent"
      >
        <Collapse.Panel
          v-for="(field, index) in form.form_schema"
          :key="field.key || index"
        >
          <template #header>
            <div class="flex min-w-0 items-center gap-2">
              <Tag color="blue">
                {{ $t(`common.announcement.fieldTypes.${field.type}`) }}
              </Tag>
              <span class="truncate">
                {{ field.label || field.key || $t('common.name') }}
              </span>
            </div>
          </template>

          <template #extra>
            <Space @click.stop>
              <Button
                :disabled="locked || index === 0"
                size="small"
                type="text"
                @click="moveField(index, -1)"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:arrow-up" class="size-3.5" />
                </template>
              </Button>
              <Button
                :disabled="locked || index === form.form_schema.length - 1"
                size="small"
                type="text"
                @click="moveField(index, 1)"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:arrow-down" class="size-3.5" />
                </template>
              </Button>
              <Button
                :disabled="locked"
                danger
                size="small"
                type="text"
                @click="removeField(index)"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
                </template>
              </Button>
            </Space>
          </template>

          <div class="grid gap-3 md:grid-cols-2">
            <Form.Item :label="$t('common.announcement.fieldKey')" required>
              <Input
                :value="field.key"
                :disabled="locked"
                @update:value="(value) => patchField(index, { key: value })"
              />
            </Form.Item>

            <Form.Item :label="$t('common.announcement.fieldLabel')" required>
              <Input
                :value="field.label"
                :disabled="locked"
                @update:value="(value) => patchField(index, { label: value })"
              />
            </Form.Item>

            <Form.Item :label="$t('common.announcement.required')">
              <Switch
                :checked="field.required"
                :disabled="locked"
                @update:checked="
                  (value) => patchField(index, { required: Boolean(value) })
                "
              />
            </Form.Item>

            <Form.Item
              v-if="field.type === 'consent'"
              :label="$t('common.announcement.mustBeTrue')"
            >
              <Switch
                :checked="field.must_be_true === true"
                :disabled="locked"
                @update:checked="
                  (value) => patchField(index, { must_be_true: Boolean(value) })
                "
              />
            </Form.Item>

            <Form.Item
              v-if="field.type === 'text'"
              :label="$t('common.announcement.placeholder')"
              class="md:col-span-2"
            >
              <Input
                :value="field.placeholder"
                :disabled="locked"
                @update:value="
                  (value) => patchField(index, { placeholder: value })
                "
              />
            </Form.Item>
          </div>

          <div
            v-if="field.type === 'radio' || field.type === 'checkbox'"
            class="space-y-2"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-medium">
                {{ $t('common.announcement.options') }}
              </span>
              <Button
                :disabled="locked"
                size="small"
                type="link"
                @click="addOption(index)"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:plus" class="size-3.5" />
                </template>
                {{ $t('common.add') }}
              </Button>
            </div>

            <div
              v-for="(option, optionIndex) in field.options ?? []"
              :key="`${field.key}-${optionIndex}`"
              class="grid gap-2 md:grid-cols-[1fr_1fr_auto]"
            >
              <Input
                :value="option.label"
                :disabled="locked"
                :placeholder="$t('common.announcement.optionLabel')"
                @update:value="
                  (value) => patchOption(index, optionIndex, { label: value })
                "
              />
              <Input
                :value="option.value"
                :disabled="locked"
                :placeholder="$t('common.announcement.optionValue')"
                @update:value="
                  (value) => patchOption(index, optionIndex, { value })
                "
              />
              <Button
                :disabled="locked"
                danger
                type="text"
                @click="removeOption(index, optionIndex)"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:x" class="size-4" />
                </template>
              </Button>
            </div>
          </div>
        </Collapse.Panel>
      </Collapse>

      <div
        v-else
        class="rounded border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground"
      >
        {{ $t('common.announcement.emptyFields') }}
      </div>
    </div>
  </Form>
</template>
