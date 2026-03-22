<script setup lang="ts">
import GlobalPreferencePage from '#/components/business/preference-page/GlobalPreferencePage.vue';

defineOptions({ name: 'TenantGlobalPreferences' });
</script>

<template>
  <GlobalPreferencePage side="tenant" api-prefix="/tenant" />
</template>
