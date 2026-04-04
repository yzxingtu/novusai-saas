<script setup lang="ts">
import { IconifyIcon } from '@vben/icons';

import { Card, Empty, Spin } from 'ant-design-vue';

import { $t as t } from '#/locales';

interface GroupNavItem {
  code: string;
  displayDesc?: string;
  displayName: string;
  icon?: string;
}

interface Props {
  activeGroup: string;
  groups: GroupNavItem[];
  loading?: boolean;
}

defineOptions({ name: 'ConfigGroupSidebar' });

withDefaults(defineProps<Props>(), {
  loading: false,
});

const emit = defineEmits<{
  select: [code: string];
}>();

function onSelect(code: string) {
  emit('select', code);
}
</script>

<template>
  <Card
    class="w-full flex-shrink-0 overflow-hidden md:w-[260px]"
    :body-style="{
      padding: 0,
      height: 'calc(100% - 57px)',
      overflow: 'auto',
    }"
  >
    <template #title>
      <div class="flex items-center gap-2">
        <IconifyIcon icon="lucide:settings" class="h-4 w-4 text-primary" />
        <span>{{ t('shared.config.page.title') }}</span>
      </div>
    </template>

    <Spin :spinning="loading" class="h-full">
      <div class="py-2">
        <div
          v-for="group in groups"
          :key="group.code"
          v-memo="[
            group.code === activeGroup,
            group.displayName,
            group.displayDesc,
            group.icon,
          ]"
          class="group-item mx-2 mb-1 cursor-pointer rounded-lg px-3 py-2.5 transition-colors"
          :class="[
            group.code === activeGroup
              ? 'bg-primary/10 text-primary'
              : 'hover:bg-accent',
          ]"
          @click="onSelect(group.code)"
        >
          <div class="flex items-center gap-2 font-medium">
            <IconifyIcon
              v-if="group.icon"
              :icon="group.icon"
              class="h-4 w-4 flex-shrink-0"
            />
            <span>{{ group.displayName }}</span>
          </div>
          <div
            v-if="group.displayDesc"
            class="mt-0.5 text-xs text-muted-foreground"
            :class="group.icon ? 'ml-6' : ''"
          >
            {{ group.displayDesc }}
          </div>
        </div>

        <Empty
          v-if="!loading && groups.length === 0"
          :description="t('shared.common.noData')"
          class="py-8"
        />
      </div>
    </Spin>
  </Card>
</template>

<style scoped>
.group-item.active {
  font-weight: 500;
}
</style>
