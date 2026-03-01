<script lang="ts" setup>
defineOptions({ name: 'TenantAIConfig' });

import { Page } from '@vben/common-ui';

import Models from '../models/index.vue';
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <Models />
  </Page>
</template>
