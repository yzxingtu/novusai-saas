<script lang="ts" setup>
import type {
  AttachmentDetailSection,
} from './types';

import { Descriptions, DescriptionsItem, Tag } from 'ant-design-vue';

interface Props {
  sections: AttachmentDetailSection[];
}

defineProps<Props>();

function visibleFields(section: AttachmentDetailSection) {
  return section.fields.filter((field) => field.show !== false);
}
</script>

<template>
  <Descriptions
    v-for="(section, sectionIndex) in sections"
    :key="section.title || sectionIndex"
    :title="section.title"
    :column="1"
    bordered
    size="small"
    :class="sectionIndex > 0 ? 'mt-4' : ''"
  >
    <DescriptionsItem
      v-for="field in visibleFields(section)"
      :key="field.label"
      :label="field.label"
    >
      <template v-if="field.kind === 'code'">
        <code class="rounded bg-accent px-1 py-0.5 text-xs">
          {{ field.value }}
        </code>
      </template>
      <template v-else-if="field.kind === 'tag'">
        <Tag :color="field.color">
          {{ field.value }}
        </Tag>
      </template>
      <template v-else>
        {{ field.value }}
      </template>
    </DescriptionsItem>
  </Descriptions>
</template>
