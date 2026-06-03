<script setup lang="ts">
import GlobalPreferencePage from '#/components/business/preference-page/GlobalPreferencePage.vue';

defineOptions({ name: 'AdminGlobalPreferences' });
</script>

<template>
  <GlobalPreferencePage side="admin" api-prefix="/admin" />
</template>
