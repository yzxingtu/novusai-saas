<script setup lang="ts">
import { computed } from 'vue';

import { Drawer } from 'ant-design-vue';

import { $t } from '#/locales';

import { providePluginConfigDrawerContext } from './plugin-config-drawer/context';
import PluginConfigDrawerBody from './plugin-config-drawer/PluginConfigDrawerBody.vue';
import { usePluginConfigDrawer } from './plugin-config-drawer/use-plugin-config-drawer';

const emit = defineEmits<{ saved: [] }>();

const drawer = usePluginConfigDrawer({
  onSaved: () => {
    emit('saved');
  },
});

const { open, visible } = drawer;

providePluginConfigDrawerContext(drawer);

const drawerTitle = computed(
  () => drawer.plugin.value?.display_name || $t('admin.plugin.title'),
);

defineExpose({ open });
</script>

<template>
  <Drawer
    v-model:open="visible"
    :title="drawerTitle"
    :width="560"
    :destroy-on-close="true"
  >
    <template v-if="drawer.plugin.value">
      <PluginConfigDrawerBody />
    </template>
  </Drawer>
</template>
