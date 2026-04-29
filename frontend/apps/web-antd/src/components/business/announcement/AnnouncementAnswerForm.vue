<script lang="ts" setup>
import type {
  AnnouncementAnswers,
  AnnouncementFormField,
} from '#/types/announcement';

import { computed, ref, watch } from 'vue';

import {
  Alert,
  Checkbox,
  Form,
  Input,
  Radio,
  Typography,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { createDefaultAnnouncementAnswers } from '#/types/announcement';

defineOptions({ name: 'AnnouncementAnswerForm' });

const props = defineProps<{
  modelValue: AnnouncementAnswers;
  readonly?: boolean;
  schema: AnnouncementFormField[];
}>();

const emit = defineEmits<{
  'update:modelValue': [value: AnnouncementAnswers];
}>();

const answers = ref<AnnouncementAnswers>({});

const hasSchema = computed(() => props.schema.length > 0);

watch(
  () => props.schema,
  (schema) => {
    answers.value = {
      ...createDefaultAnnouncementAnswers(schema),
      ...props.modelValue,
    };
    emit('update:modelValue', answers.value);
  },
  { deep: true, immediate: true },
);

watch(
  () => props.modelValue,
  (value) => {
    answers.value = {
      ...answers.value,
      ...value,
    };
  },
  { deep: true },
);

function updateAnswer(key: string, value: boolean | string | string[]) {
  answers.value = {
    ...answers.value,
    [key]: value,
  };
  emit('update:modelValue', answers.value);
}

function updateArrayAnswer(key: string, value: unknown) {
  updateAnswer(key, Array.isArray(value) ? value.map(String) : []);
}

function getStringArrayAnswer(key: string): string[] {
  const value = answers.value[key];
  return Array.isArray(value) ? value.map(String) : [];
}
</script>

<template>
  <div class="space-y-4">
    <Alert
      v-if="!hasSchema"
      :message="$t('common.announcement.noResponseFields')"
      type="info"
      show-icon
    />

    <Form v-else layout="vertical">
      <Form.Item
        v-for="field in schema"
        :key="field.key"
        :label="field.label"
        :required="field.required || field.must_be_true"
      >
        <Checkbox
          v-if="field.type === 'consent'"
          :checked="answers[field.key] === true"
          :disabled="readonly"
          @update:checked="(value) => updateAnswer(field.key, Boolean(value))"
        >
          {{ field.label }}
        </Checkbox>

        <Input.TextArea
          v-else-if="field.type === 'text'"
          :value="String(answers[field.key] ?? '')"
          :disabled="readonly"
          :placeholder="
            field.placeholder || $t('common.announcement.answerPlaceholder')
          "
          :rows="3"
          @update:value="(value) => updateAnswer(field.key, value)"
        />

        <Radio.Group
          v-else-if="field.type === 'radio'"
          :value="answers[field.key]"
          :disabled="readonly"
          :options="field.options ?? []"
          @update:value="(value) => updateAnswer(field.key, value)"
        />

        <Checkbox.Group
          v-else-if="field.type === 'checkbox'"
          :value="getStringArrayAnswer(field.key)"
          :disabled="readonly"
          :options="field.options ?? []"
          @update:value="(value) => updateArrayAnswer(field.key, value)"
        />

        <Typography.Text v-if="field.required" type="secondary">
          {{ $t('common.required') }}
        </Typography.Text>
      </Form.Item>
    </Form>
  </div>
</template>
