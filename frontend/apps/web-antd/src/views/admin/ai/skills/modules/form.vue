<script lang="ts" setup>
import SkillFormShell from './SkillFormShell.vue';

defineOptions({ name: 'AdminSkillForm' });

const emit = defineEmits<{ success: [] }>();
</script>

<template>
  <SkillFormShell v-bind="$attrs" @success="emit('success')" />
</template>
