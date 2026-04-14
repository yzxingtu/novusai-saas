<script lang="ts" setup>
import type { Component } from 'vue';

import type { ActionLogDetailController } from '../use-action-log-detail';

import { Card } from 'ant-design-vue';

import ActionLogDetailDrawer from './ActionLogDetailDrawer.vue';
import ActionLogGrid from './ActionLogGrid.vue';

defineOptions({ name: 'ActionLogTableSection' });

defineProps<{
  controller: ActionLogDetailController;
  gridComponent: Component;
}>();
</script>

<template>
  <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
    <ActionLogGrid :grid-component="gridComponent" />
  </Card>

  <ActionLogDetailDrawer :controller="controller" />
</template>
