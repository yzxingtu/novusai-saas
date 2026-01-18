<script lang="ts" setup>
/**
 * 套餐管理入口
 * 对应后端菜单 component: "tenant/Plans"
 */
import { defineAsyncComponent } from 'vue';

const PlanList = defineAsyncComponent(() => import('./plans/index.vue'));
</script>

<template>
  <PlanList />
</template>
