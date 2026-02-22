<script lang="ts" setup>
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Carousel,
  Descriptions,
  Divider,
  Drawer,
  Image,
  Popconfirm,
  Skeleton,
  Tag,
} from 'ant-design-vue';

import type { MarketplacePlugin } from '#/api/admin/marketplace';

import { getMarketplaceDetailApi } from '#/api/admin/marketplace';
import { $t } from '#/locales';

defineOptions({ name: 'MarketplaceDetailDrawer' });

const props = defineProps<{
  plugin: MarketplacePlugin | null;
  installingSlug: string | null;
}>();

const emit = defineEmits<{
  refresh: [];
  install: [plugin: MarketplacePlugin];
  update: [plugin: MarketplacePlugin];
}>();

const open = defineModel<boolean>('open', { default: false });

const loading = ref(false);
const readme = ref<string | null>(null);
const repoUrl = ref<string | null>(null);

const isInstalling = computed(
  () => !!props.plugin && props.installingSlug === props.plugin.slug,
);

// ============================================================
// Load detail (README)
// ============================================================

async function loadDetail(slug: string) {
  loading.value = true;
  readme.value = null;
  repoUrl.value = null;
  try {
    const detail = await getMarketplaceDetailApi(slug);
    readme.value = detail.readme || null;
    repoUrl.value = detail.repo_url || null;
  } catch {
    // silently fail
  } finally {
    loading.value = false;
  }
}

watch(
  () => [open.value, props.plugin?.slug],
  ([isOpen, slug]) => {
    if (isOpen && slug) {
      loadDetail(slug as string);
    }
  },
);

// ============================================================
// Actions
// ============================================================

function handleInstall() {
  if (props.plugin) {
    emit('install', props.plugin);
  }
}

function handleUpdate() {
  if (props.plugin) {
    emit('update', props.plugin);
  }
}

// ============================================================
// Markdown rendering (simple)
// ============================================================

function sanitizeHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/<object[\s\S]*?<\/object>/gi, '')
    .replace(/<embed[\s\S]*?>/gi, '')
    .replace(/\son\w+\s*=/gi, ' data-removed=')
    .replace(/javascript\s*:/gi, '');
}

function renderMarkdown(md: string): string {
  const html = md
    .replace(/^### (.+)$/gm, '<h3 class="text-foreground mt-4 mb-2 text-base font-semibold">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-foreground mt-5 mb-2 text-lg font-bold">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-foreground mt-6 mb-3 text-xl font-bold">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="bg-muted rounded px-1.5 py-0.5 text-xs">$1</code>')
    .replace(/^```(\w*)\n([\s\S]*?)```$/gm, '<pre class="bg-muted my-3 overflow-x-auto rounded-lg p-4 text-sm"><code>$2</code></pre>')
    .replace(/^- (.+)$/gm, '<li class="text-muted-foreground ml-4 list-disc text-sm">$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li class="text-muted-foreground ml-4 list-decimal text-sm">$1</li>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline">$1</a>');
  return sanitizeHtml(html);
}
</script>

<template>
  <Drawer
    v-model:open="open"
    :title="$t('admin.system.marketplace.detail.title')"
    width="680"
    placement="right"
    :destroy-on-close="true"
  >
    <template v-if="plugin">
      <!-- Header -->
      <div class="mb-6 flex items-start gap-4">
        <div class="bg-primary/10 flex h-14 w-14 shrink-0 items-center justify-center rounded-xl">
          <IconifyIcon
            :icon="plugin.icon || 'lucide:puzzle'"
            class="text-primary h-8 w-8"
          />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <h2 class="text-foreground truncate text-xl font-bold">
              {{ plugin.display_name }}
            </h2>
            <Badge
              v-if="plugin.official"
              :count="$t('admin.system.marketplace.official')"
              :number-style="{ backgroundColor: 'var(--primary)', fontSize: '11px' }"
            />
            <Tag v-else color="default" class="!m-0 !text-xs">
              {{ $t('admin.system.marketplace.community') }}
            </Tag>
          </div>
          <p class="text-muted-foreground mt-1 text-sm">
            {{ plugin.description }}
          </p>
        </div>
      </div>

      <!-- Metadata -->
      <Descriptions :column="2" size="small" class="mb-5" bordered>
        <Descriptions.Item :label="$t('admin.system.marketplace.detail.version')">
          <Tag color="blue">v{{ plugin.version }}</Tag>
          <span
            v-if="plugin.installed_version && plugin.install_status === 'update_available'"
            class="text-muted-foreground ml-1 text-xs"
          >
            ({{ $t('admin.system.marketplace.status.installed') }}: v{{ plugin.installed_version }})
          </span>
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.system.marketplace.detail.author')">
          {{ plugin.author || '-' }}
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.system.marketplace.detail.category')">
          <Tag v-if="plugin.category">
            {{ $t(`admin.system.marketplace.category.${plugin.category}`, plugin.category) }}
          </Tag>
          <span v-else>-</span>
        </Descriptions.Item>
        <Descriptions.Item :label="$t('admin.system.marketplace.detail.pluginType')">
          <Tag>{{ plugin.plugin_type }}</Tag>
        </Descriptions.Item>
        <Descriptions.Item
          v-if="plugin.license"
          :label="$t('admin.system.marketplace.detail.license')"
        >
          {{ plugin.license }}
        </Descriptions.Item>
        <Descriptions.Item
          v-if="plugin.min_platform_version"
          :label="$t('admin.system.marketplace.detail.platform')"
        >
          {{ plugin.min_platform_version }}
        </Descriptions.Item>
      </Descriptions>

      <!-- Tags -->
      <div v-if="plugin.tags && plugin.tags.length > 0" class="mb-5">
        <div class="text-foreground mb-2 text-sm font-medium">
          {{ $t('admin.system.marketplace.detail.tags') }}
        </div>
        <div class="flex flex-wrap gap-1.5">
          <Tag v-for="tag in plugin.tags" :key="tag" color="default">
            {{ tag }}
          </Tag>
        </div>
      </div>

      <!-- Repository Link -->
      <div v-if="repoUrl" class="mb-5">
        <div class="text-foreground mb-2 text-sm font-medium">
          {{ $t('admin.system.marketplace.detail.repository') }}
        </div>
        <a
          :href="repoUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="text-primary inline-flex items-center gap-1.5 text-sm hover:underline"
        >
          <IconifyIcon icon="lucide:external-link" class="h-3.5 w-3.5" />
          {{ $t('admin.system.marketplace.detail.viewSource') }}
        </a>
      </div>

      <!-- Screenshots -->
      <div
        v-if="plugin.screenshots && plugin.screenshots.length > 0"
        class="mb-5"
      >
        <div class="text-foreground mb-2 text-sm font-medium">
          {{ $t('admin.system.marketplace.detail.screenshots') }}
        </div>
        <Carousel autoplay dots-class="custom-dots">
          <div v-for="(url, idx) in plugin.screenshots" :key="idx">
            <Image :src="url" class="rounded-lg" />
          </div>
        </Carousel>
      </div>

      <Divider />

      <!-- README -->
      <div class="readme-section">
        <Skeleton v-if="loading" active :paragraph="{ rows: 8 }" />
        <div v-else-if="readme" class="readme-content" v-html="renderMarkdown(readme)" />
        <div v-else class="text-muted-foreground py-10 text-center text-sm">
          {{ $t('admin.system.marketplace.detail.noReadme') }}
        </div>
      </div>
    </template>

    <!-- Footer -->
    <template #footer>
      <div v-if="plugin" class="flex items-center justify-end gap-3">
        <!-- Not installed -->
        <template v-if="plugin.install_status === 'not_installed'">
          <Popconfirm
            v-if="!plugin.official"
            :title="$t('admin.system.marketplace.confirmInstall')"
            :description="$t('admin.system.marketplace.confirmCommunityInstall')"
            @confirm="handleInstall"
            :ok-text="$t('admin.system.marketplace.install')"
          >
            <Button
              type="primary"
              size="large"
              :loading="isInstalling"
            >
              <template v-if="!isInstalling" #icon>
                <IconifyIcon icon="lucide:download" />
              </template>
              {{
                isInstalling
                  ? $t('admin.system.marketplace.installing')
                  : $t('admin.system.marketplace.install')
              }}
            </Button>
          </Popconfirm>
          <Button
            v-else
            type="primary"
            size="large"
            :loading="isInstalling"
            @click="handleInstall"
          >
            <template v-if="!isInstalling" #icon>
              <IconifyIcon icon="lucide:download" />
            </template>
            {{
              isInstalling
                ? $t('admin.system.marketplace.installing')
                : $t('admin.system.marketplace.install')
            }}
          </Button>
        </template>

        <!-- Installed -->
        <Tag
          v-else-if="plugin.install_status === 'installed'"
          color="success"
          class="!m-0 !py-1 !px-4 !text-sm"
        >
          <template #icon>
            <IconifyIcon icon="lucide:check-circle" />
          </template>
          {{ $t('admin.system.marketplace.installed') }}
        </Tag>

        <!-- Update available -->
        <Popconfirm
          v-else-if="plugin.install_status === 'update_available'"
          :title="$t('admin.system.marketplace.confirmUpdate')"
          :description="$t('admin.system.marketplace.confirmUpdateContent', {
            name: plugin.display_name,
            current: plugin.installed_version,
            target: plugin.version,
          })"
          @confirm="handleUpdate"
          :ok-text="$t('admin.system.marketplace.update', { version: plugin.version })"
        >
          <Button
            size="large"
            class="!border-warning !text-warning hover:!bg-warning/10"
            :loading="isInstalling"
          >
            <template v-if="!isInstalling" #icon>
              <IconifyIcon icon="lucide:arrow-up-circle" />
            </template>
            {{
              isInstalling
                ? $t('admin.system.marketplace.updating')
                : $t('admin.system.marketplace.update', { version: plugin.version })
            }}
          </Button>
        </Popconfirm>
      </div>
    </template>
  </Drawer>
</template>

<style scoped>
.readme-content :deep(h1),
.readme-content :deep(h2),
.readme-content :deep(h3) {
  color: var(--foreground);
}

.readme-content :deep(a) {
  color: var(--primary);
}

.readme-content :deep(code) {
  background: var(--muted);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 0.85em;
}

.readme-content :deep(pre) {
  background: var(--muted);
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
}

.readme-content :deep(pre code) {
  background: none;
  padding: 0;
}

.readme-content :deep(li) {
  margin-bottom: 4px;
}
</style>
