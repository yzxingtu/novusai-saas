<script lang="ts" setup>
import { Page } from '@vben/common-ui';

import Models from '../models/index.vue';

defineOptions({ name: 'TenantAIConfig' });
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <Models />
  </Page>
</template>
