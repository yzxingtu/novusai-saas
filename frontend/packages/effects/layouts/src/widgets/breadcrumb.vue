<script lang="ts" setup>
import type { BreadcrumbStyleType } from '@vben/types';

import type { IBreadcrumb } from '@vben-core/shadcn-ui';

import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { $t, $te, useI18n } from '@vben/locales';
import { useAccessStore } from '@vben/stores';
import { resolveRouteMetaTitle } from '@vben/utils';

import { VbenBreadcrumbView } from '@vben-core/shadcn-ui';

interface Props {
  hideWhenOnlyOne?: boolean;
  showHome?: boolean;
  showIcon?: boolean;
  type?: BreadcrumbStyleType;
}

const props = withDefaults(defineProps<Props>(), {
  showHome: false,
  showIcon: false,
  type: 'normal',
});

const route = useRoute();
const router = useRouter();
const accessStore = useAccessStore();
const { locale } = useI18n();

const breadcrumbs = computed((): IBreadcrumb[] => {
  const currentLocale = locale.value;
  const matched = route.matched;

  const resultBreadcrumb: IBreadcrumb[] = [];

  for (const match of matched) {
    const { meta, path } = match;
    const { hideChildrenInMenu, hideInBreadcrumb, icon } = meta || {};
    if (hideInBreadcrumb || hideChildrenInMenu || !path) {
      continue;
    }

    // 从 accessMenus 获取已翻译的标题，因为切换语言时 accessMenus 会重新加载
    const menu = accessStore.getMenuByPath(path);
    const resolvedTitle = resolveRouteMetaTitle(meta, {
      hasLocaleKey: $te,
      locale: currentLocale,
      translate: $t,
    });
    const menuTitle = menu?.name || resolvedTitle;

    resultBreadcrumb.push({
      icon: menu?.icon || icon,
      path: path || route.path,
      title: menuTitle as string,
    });
  }
  if (props.showHome) {
    resultBreadcrumb.unshift({
      icon: 'lucide:home',
      isHome: true,
      path: '/',
    });
  }
  if (props.hideWhenOnlyOne && resultBreadcrumb.length === 1) {
    return [];
  }

  return resultBreadcrumb;
});

function handleSelect(path: string) {
  router.push(path);
}
</script>
<template>
  <VbenBreadcrumbView
    :breadcrumbs="breadcrumbs"
    :show-icon="showIcon"
    :style-type="type"
    class="ml-2"
    @select="handleSelect"
  />
</template>
