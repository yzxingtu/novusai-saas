<script lang="ts" setup>
/**
 * 插件市场 — 与插件管理页同风格的卡片网格
 */
import type { MarketplacePluginItem } from '#/api/admin/plugin-marketplace';
import type { LocationQueryRaw } from 'vue-router';

import { onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Input,
  message,
  Modal,
  Pagination,
  Select,
  SelectOption,
  Spin,
  Tag,
} from 'ant-design-vue';

import {
  getMarketplaceListApi,
  marketplaceConfirmInstallApi,
} from '#/api/admin/plugin-marketplace';
import { usePageAIRegistration } from '#/composables/use-page-ai-registration';
import { $t } from '#/locales';

import { getTierColor, getTierText } from '../data';
import MarketplaceSettingsModal from './MarketplaceSettingsModal.vue';
import SkillRegistryPanel from './SkillRegistryPanel.vue';

defineOptions({ name: 'AdminPluginMarketplace' });

const router = useRouter();
const route = useRoute();
const settingsRef = ref<InstanceType<typeof MarketplaceSettingsModal>>();
const plugins = ref<MarketplacePluginItem[]>([]);
const loading = ref(false);
const searchKeyword = ref('');
const sortBy = ref('-downloads');
const filterCategory = ref('all');
const total = ref(0);
const currentPage = ref(1);
const activeCatalog = ref<'plugins' | 'skills'>('plugins');

const CATEGORIES = [
  {
    value: 'all',
    icon: 'lucide:grid-2x2',
    label: () => $t('admin.plugin.type_options.all'),
  },
  {
    value: 'ai',
    icon: 'lucide:brain',
    label: () => $t('admin.plugin.marketplace.category.ai'),
  },
  {
    value: 'integration',
    icon: 'lucide:link',
    label: () => $t('admin.plugin.marketplace.category.integration'),
  },
  {
    value: 'storage',
    icon: 'lucide:database',
    label: () => $t('admin.plugin.marketplace.category.storage'),
  },
  {
    value: 'business',
    icon: 'lucide:briefcase',
    label: () => $t('admin.plugin.marketplace.category.business'),
  },
  {
    value: 'tools',
    icon: 'lucide:wrench',
    label: () => $t('admin.plugin.marketplace.category.tools'),
  },
  {
    value: 'communication',
    icon: 'lucide:message-circle',
    label: () => $t('admin.plugin.marketplace.category.communication'),
  },
  {
    value: 'analytics',
    icon: 'lucide:bar-chart-3',
    label: () => $t('admin.plugin.marketplace.category.analytics'),
  },
  {
    value: 'security',
    icon: 'lucide:shield',
    label: () => $t('admin.plugin.marketplace.category.security'),
  },
] as const;

async function loadMarketplace() {
  loading.value = true;
  try {
    const res = (await getMarketplaceListApi({
      search: searchKeyword.value,
      sort: sortBy.value,
      category: filterCategory.value === 'all' ? '' : filterCategory.value,
      page_number: currentPage.value,
      page_size: 24,
    })) as unknown as { items: MarketplacePluginItem[]; total: number };
    plugins.value = res?.items || [];
    total.value = res?.total || 0;
  } catch {
    plugins.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(loadMarketplace);

watch(
  () => route.query.catalog,
  (catalog) => {
    activeCatalog.value = catalog === 'skills' ? 'skills' : 'plugins';
  },
  { immediate: true },
);

function switchCatalog(next: 'plugins' | 'skills') {
  activeCatalog.value = next;
  const nextQuery: LocationQueryRaw = { ...route.query };
  if (next === 'skills') {
    nextQuery.catalog = 'skills';
  } else {
    delete nextQuery.catalog;
  }
  router.replace({
    query: nextQuery,
  });
}

function handleSearch() {
  currentPage.value = 1;
  loadMarketplace();
}

async function handleInstall(plugin: MarketplacePluginItem) {
  const slug = plugin.slug || plugin.name;
  Modal.confirm({
    title: $t('admin.plugin.marketplace.confirmInstall'),
    content: `${plugin.display_name || plugin.name} v${plugin.version}`,
    async onOk() {
      try {
        await marketplaceConfirmInstallApi(slug);
        message.success($t('admin.plugin.messages.installSuccess'));
        await loadMarketplace();
      } catch {
        message.error($t('admin.plugin.messages.installFailed'));
      }
    },
  });
}

usePageAIRegistration({
  pageKey: 'admin.plugins.marketplace',
  title: () => $t('admin.plugin.marketplace.title'),
  resource: '/admin/plugins/marketplace',
  data: () => ({
    total: total.value,
  }),
  operations: [
    {
      name: 'refresh_marketplace',
      label: $t('shared.pageOperation.refreshList'),
      description: 'Reload the plugin marketplace list',
      readonly: true,
      handler: async () => {
        await loadMarketplace();
        return { success: true, message: 'Marketplace refreshed' };
      },
    },
    {
      name: 'search',
      label: $t('shared.pageOperation.searchPlugins'),
      description: 'Search plugins in the marketplace',
      readonly: true,
      params: {
        keyword: { type: 'string', description: 'Plugin name keyword' },
      },
      handler: async (params) => {
        searchKeyword.value = (params?.keyword as string) || '';
        currentPage.value = 1;
        await loadMarketplace();
        return {
          success: true,
          message: `Searched for: ${searchKeyword.value}`,
        };
      },
    },
  ],
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-5">
    <!-- ===== 顶部 Hero 区域 ===== -->
    <div
      class="relative !h-auto min-h-[180px] overflow-hidden rounded-2xl bg-gradient-to-br from-primary/5 via-background to-primary/5 p-6"
    >
      <div
        class="relative z-10 flex flex-wrap items-start justify-between gap-4"
      >
        <div>
          <div class="flex items-center gap-2">
            <button
              class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              @click="router.push('/admin/plugins')"
            >
              <IconifyIcon icon="lucide:arrow-left" class="size-4" />
            </button>
            <h1 class="text-xl font-bold text-foreground">
              {{ $t('admin.plugin.marketplace.combinedTitle') }}
            </h1>
          </div>
          <p class="mt-1 pl-10 text-sm text-muted-foreground">
            {{
              activeCatalog === 'plugins'
                ? $t('admin.plugin.marketplace.searchPlaceholder')
                : $t('admin.plugin.marketplace.skillSubtitle')
            }}
          </p>
        </div>
        <!-- 搜索 + 排序 + 设置 -->
        <div class="flex items-center gap-3">
          <Button
            type="text"
            size="large"
            class="!text-muted-foreground hover:!text-foreground"
            @click="settingsRef?.open()"
          >
            <IconifyIcon icon="lucide:settings" class="size-5" />
          </Button>
          <Input.Search
            v-if="activeCatalog === 'plugins'"
            v-model:value="searchKeyword"
            :placeholder="$t('admin.plugin.marketplace.searchPlaceholder')"
            allow-clear
            class="!w-64 !rounded-lg"
            @search="handleSearch"
          />
          <Select
            v-if="activeCatalog === 'plugins'"
            v-model:value="sortBy"
            class="!min-w-[140px]"
            @change="handleSearch"
          >
            <SelectOption value="-downloads">
              {{ $t('admin.plugin.marketplace.sortDownloads') }}
            </SelectOption>
            <SelectOption value="-rating">
              {{ $t('admin.plugin.marketplace.sortRating') }}
            </SelectOption>
            <SelectOption value="-updated">
              {{ $t('admin.plugin.marketplace.sortUpdated') }}
            </SelectOption>
          </Select>
        </div>
      </div>
      <!-- 装饰背景 -->
      <div
        class="absolute -right-12 -top-12 size-48 rounded-full bg-primary/5 blur-3xl"
      ></div>
      <div
        class="absolute -bottom-8 -left-8 size-32 rounded-full bg-primary/10 blur-2xl"
      ></div>
    </div>

    <MarketplaceSettingsModal ref="settingsRef" @saved="loadMarketplace" />

    <div class="flex items-center gap-1.5">
      <button
        class="flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-medium transition-all"
        :class="
          activeCatalog === 'plugins'
            ? 'border-primary/30 bg-primary/10 text-primary'
            : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground'
        "
        @click="switchCatalog('plugins')"
      >
        <IconifyIcon icon="lucide:store" class="size-4" />
        <span>{{ $t('admin.plugin.marketplace.tabPlugins') }}</span>
      </button>
      <button
        v-access:code="['plugin_skill_registry:list']"
        class="flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-medium transition-all"
        :class="
          activeCatalog === 'skills'
            ? 'border-primary/30 bg-primary/10 text-primary'
            : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground'
        "
        @click="switchCatalog('skills')"
      >
        <IconifyIcon icon="lucide:package-search" class="size-4" />
        <span>{{ $t('admin.plugin.marketplace.tabSkills') }}</span>
      </button>
    </div>

    <!-- ===== 分类筛选 ===== -->
    <div v-if="activeCatalog === 'plugins'" class="flex items-center gap-1.5">
      <button
        v-for="cat in CATEGORIES"
        :key="cat.value"
        class="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-all duration-200"
        :class="
          filterCategory === cat.value
            ? 'border-primary/30 bg-primary/10 text-primary'
            : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground'
        "
        @click="
          filterCategory = cat.value;
          handleSearch();
        "
      >
        <IconifyIcon :icon="cat.icon" class="size-3" />
        <span>{{ cat.label() }}</span>
      </button>
    </div>

    <!-- ===== 插件卡片网格 ===== -->
    <template v-if="activeCatalog === 'plugins'">
      <Spin :spinning="loading">
      <div
        v-if="plugins.length > 0"
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
      >
        <div
          v-for="p in plugins"
          :key="p.slug || p.name"
          class="group relative cursor-pointer overflow-hidden rounded-2xl border border-border/60 bg-card transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5"
        >
          <!-- 顶部状态条 -->
          <div
            class="h-1 w-full"
            :class="
              p.is_installed
                ? 'bg-gradient-to-r from-emerald-400 to-emerald-500'
                : 'bg-gradient-to-r from-primary/40 to-primary/60'
            "
          ></div>

          <div class="p-5">
            <!-- 头部：图标 + 名称 + 版本 -->
            <div class="mb-3.5 flex items-start gap-3.5">
              <div
                class="flex size-12 shrink-0 items-center justify-center rounded-xl shadow-sm transition-all duration-200 group-hover:shadow-md"
                :class="
                  p.is_installed
                    ? 'bg-gradient-to-br from-emerald-500/15 to-emerald-500/5'
                    : 'bg-gradient-to-br from-primary/15 to-primary/5'
                "
              >
                <IconifyIcon
                  :icon="
                    p.icon && p.icon.includes(':') ? p.icon : 'lucide:puzzle'
                  "
                  class="size-5.5"
                  :class="p.is_installed ? 'text-emerald-600' : 'text-primary'"
                />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span
                    class="truncate text-[15px] font-semibold leading-snug text-foreground"
                  >
                    {{ p.display_name || p.name }}
                  </span>
                  <Tag
                    v-if="p.is_installed"
                    color="success"
                    class="!m-0 !rounded-md !border-0 !text-[10px]"
                  >
                    {{ $t('admin.plugin.marketplace.installed') }}
                  </Tag>
                </div>
                <div
                  class="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground"
                >
                  <span class="font-mono">v{{ p.version }}</span>
                  <template v-if="p.author">
                    <span class="text-border">·</span>
                    <span>{{ p.author }}</span>
                  </template>
                </div>
              </div>
            </div>

            <!-- 描述 -->
            <p
              class="mb-4 line-clamp-2 min-h-[2.25rem] text-[13px] leading-relaxed text-muted-foreground/80"
            >
              {{ p.description || '-' }}
            </p>

            <!-- 标签行 -->
            <div class="mb-4 flex flex-wrap items-center gap-1.5">
              <Tag
                :color="getTierColor(p.tier)"
                class="!m-0 !rounded-md !border-0 !text-[11px]"
              >
                {{ getTierText(p.tier) }}
              </Tag>
              <Tag
                v-for="tag in (p.tags || []).slice(0, 2)"
                :key="tag"
                class="!m-0 !rounded-md !border-0 !text-[11px]"
              >
                {{ tag }}
              </Tag>
            </div>

            <!-- 底部操作栏 -->
            <div
              class="flex items-center justify-between border-t border-border/40 pt-3.5"
              @click.stop
            >
              <div
                class="flex items-center gap-3 text-xs text-muted-foreground"
              >
                <span class="flex items-center gap-1">
                  <IconifyIcon icon="lucide:download" class="size-3.5" />
                  {{ p.downloads || 0 }}
                </span>
                <span v-if="p.rating" class="flex items-center gap-1">
                  <IconifyIcon
                    icon="lucide:star"
                    class="size-3.5 text-yellow-500"
                  />
                  {{ p.rating }}
                </span>
              </div>
              <Button
                v-if="!p.is_installed"
                type="primary"
                size="small"
                class="!rounded-lg !shadow-sm !shadow-primary/20"
                @click="handleInstall(p)"
              >
                <IconifyIcon icon="lucide:download" class="mr-1 size-3.5" />
                {{ $t('admin.plugin.marketplace.install') }}
              </Button>
              <span
                v-else
                class="flex items-center gap-1 text-xs text-emerald-600"
              >
                <IconifyIcon icon="lucide:circle-check" class="size-3.5" />
                v{{ p.installed_version || p.version }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div
        v-if="plugins.length > 0 && total > 24"
        class="mt-6 flex justify-center"
      >
        <Pagination
          v-model:current="currentPage"
          :total="total"
          :page-size="24"
          show-size-changer
          @change="loadMarketplace"
        />
      </div>

      <!-- 空状态 -->
      <div
        v-else-if="plugins.length === 0 && !loading"
        class="flex flex-col items-center justify-center gap-4 py-24"
      >
        <div
          class="flex size-20 items-center justify-center rounded-2xl bg-muted"
        >
          <IconifyIcon
            icon="lucide:store"
            class="size-10 text-muted-foreground/50"
          />
        </div>
        <div class="text-center">
          <p class="text-sm font-medium text-foreground">
            {{ $t('admin.plugin.marketplace.empty') }}
          </p>
        </div>
      </div>
      </Spin>
    </template>
    <div v-else v-access:code="['plugin_skill_registry:list']">
      <SkillRegistryPanel />
    </div>
  </Page>
</template>
