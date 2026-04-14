<script lang="ts" setup>
import SkillFormContent from './SkillFormContent.vue';

defineOptions({ name: 'AdminSkillFormShell' });

const emit = defineEmits<{ success: [] }>();
</script>

<template>
  <SkillFormContent v-bind="$attrs" @success="emit('success')" />
</template>
