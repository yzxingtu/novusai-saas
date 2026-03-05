<script lang="ts" setup>
import type { BreadcrumbStyleType } from '@vben/types';

import type { IBreadcrumb } from '@vben-core/shadcn-ui';

import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { $t, $te } from '@vben/locales';
import { useAccessStore } from '@vben/stores';

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

const breadcrumbs = computed((): IBreadcrumb[] => {
  const matched = route.matched;

  const resultBreadcrumb: IBreadcrumb[] = [];

  for (const match of matched) {
    const { meta, path } = match;
    const { hideChildrenInMenu, hideInBreadcrumb, icon, title } = meta || {};
    if (hideInBreadcrumb || hideChildrenInMenu || !path) {
      continue;
    }

    // 从 accessMenus 获取已翻译的标题，因为切换语言时 accessMenus 会重新加载
    const menu = accessStore.getMenuByPath(path);
    // 静态路由的 meta.title 在模块导入时通过 $t() 设置，
    // 此时 i18n 尚未就绪，值为原始 key（如 "page.auth.profile"）。
    // 动态路由的 title 由后端已翻译。此处对未匹配到动态菜单的 title 尝试运行时翻译。
    const rawTitle = (title || '') as string;
    const resolvedTitle =
      !menu && rawTitle.includes('.') && $te(rawTitle)
        ? $t(rawTitle)
        : rawTitle;
    const menuTitle = menu?.name || resolvedTitle;

    resultBreadcrumb.push({
      icon: menu?.icon || icon,
      path: path || route.path,
      title: menuTitle as string,
    });
  }
  if (props.showHome) {
    resultBreadcrumb.unshift({
      icon: 'mdi:home-outline',
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
