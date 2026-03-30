<script lang="ts" setup>
import type {
  SkillRegistryPackageItem,
  SkillRegistryUpdateItem,
} from '#/api/admin/skill-registry';

import { computed, onMounted, ref } from 'vue';

import {
  Button,
  Card,
  Empty,
  Input,
  Modal,
  Spin,
  Tag,
  message,
} from 'ant-design-vue';

import {
  batchUpgradeSkillRegistryPackagesApi,
  getSkillRegistryDetailApi,
  getSkillRegistryListApi,
  getSkillRegistryUpdatesApi,
  installSkillRegistryPackageApi,
  previewSkillRegistryUpgradeApi,
  previewSkillRegistryInstallApi,
  upgradeSkillRegistryPackageApi,
} from '#/api/admin/skill-registry';
import { $t } from '#/locales';

defineOptions({ name: 'SkillRegistryPanel' });

const loading = ref(false);
const installingSlug = ref('');
const upgradingSlug = ref('');
const keyword = ref('');
const sort = ref<'-downloads' | '-rating' | '-updated_at'>('-downloads');
const packages = ref<SkillRegistryPackageItem[]>([]);
const total = ref(0);
const detailOpen = ref(false);
const detailLoading = ref(false);
const activeDetail = ref<null | SkillRegistryPackageItem>(null);
const updatesBySlug = ref<Record<string, SkillRegistryUpdateItem>>({});
const batchUpgrading = ref(false);
const batchResultOpen = ref(false);
const batchUpgradeResult = ref<null | Awaited<
  ReturnType<typeof batchUpgradeSkillRegistryPackagesApi>
>>(null);

const stats = computed(() => {
  const installed = packages.value.filter((item) => item.is_installed).length;
  const rated = packages.value.filter((item) => Number(item.rating || 0) > 0).length;
  return {
    installed,
    rated,
    total: total.value,
    upgradable: Object.keys(updatesBySlug.value).length,
  };
});

async function loadPackages() {
  loading.value = true;
  try {
    const [result, updates] = await Promise.all([
      getSkillRegistryListApi({
        page_number: 1,
        page_size: 24,
        search: keyword.value.trim(),
        sort: sort.value,
      }),
      getSkillRegistryUpdatesApi(),
    ]);
    updatesBySlug.value = Object.fromEntries(
      (updates ?? []).map((item) => [item.slug, item]),
    );
    packages.value = (result.items ?? []).map((item) => {
      const update = updatesBySlug.value[item.slug];
      if (!update) {
        return item;
      }
      return {
        ...item,
        can_upgrade: true,
        latest_version: update.latest_version,
        source_locked: update.source_locked,
        source_url: update.source_url,
      };
    });
    total.value = Number(result.total || 0);
  } finally {
    loading.value = false;
  }
}

async function openDetail(item: SkillRegistryPackageItem) {
  detailOpen.value = true;
  detailLoading.value = true;
  activeDetail.value = null;
  try {
    const detail = await getSkillRegistryDetailApi(item.slug);
    const update = updatesBySlug.value[item.slug];
    activeDetail.value = update
      ? {
          ...detail,
          can_upgrade: true,
          installed_version: update.installed_version,
          latest_version: update.latest_version,
          source_locked: update.source_locked,
          source_url: update.source_url,
        }
      : detail;
  } finally {
    detailLoading.value = false;
  }
}

async function installPackage(item: SkillRegistryPackageItem) {
  const preview = await previewSkillRegistryInstallApi(item.slug);
  Modal.confirm({
    title: $t('admin.ai.skillRegistry.installConfirmTitle'),
    content:
      `${preview.display_name || preview.name || item.slug}\n` +
      `${$t('admin.ai.skillRegistry.version')}: ${preview.version || '-'}\n` +
      `${$t('admin.ai.skillRegistry.runtimeTruthHint')}`,
    async onOk() {
      installingSlug.value = item.slug;
      try {
        const result = await installSkillRegistryPackageApi(item.slug);
        message.success(
          $t('admin.ai.skillRegistry.installSuccess', {
            name: result.package_name,
          }),
        );
        await loadPackages();
      } finally {
        installingSlug.value = '';
      }
    },
  });
}

async function upgradePackage(item: SkillRegistryPackageItem) {
  const preview = await previewSkillRegistryUpgradeApi(item.slug);
  Modal.confirm({
    title: $t('admin.plugin.action.upgrade'),
    content:
      `${preview.display_name}\n` +
      `${preview.installed_version || '-'} -> ${preview.latest_version || '-'}\n` +
      `${preview.source_url || ''}\n\n` +
      `${preview.changelog || ''}`,
    async onOk() {
      upgradingSlug.value = item.slug;
      try {
        await upgradeSkillRegistryPackageApi(item.slug);
        message.success($t('admin.plugin.messages.upgradeSuccess'));
        await loadPackages();
      } finally {
        upgradingSlug.value = '';
      }
    },
  });
}

async function batchUpgradePackages() {
  batchUpgrading.value = true;
  try {
    const result = await batchUpgradeSkillRegistryPackagesApi();
    batchUpgradeResult.value = result;
    batchResultOpen.value = true;
    if ((result.failed || []).length > 0) {
      message.warning(
        `${$t('admin.plugin.messages.upgradeSuccess')} / failed: ${result.failed.length}`,
      );
    } else {
      message.success($t('admin.plugin.messages.upgradeSuccess'));
    }
    await loadPackages();
  } finally {
    batchUpgrading.value = false;
  }
}

onMounted(loadPackages);
</script>

<template>
  <div class="space-y-4">
    <section class="rounded-3xl border border-border bg-background p-4 shadow-sm">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-3">
          <div class="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
            <span class="size-2 rounded-full bg-sky-500"></span>
            {{ $t('admin.ai.skillRegistry.badge') }}
          </div>
          <div class="space-y-2">
            <h2 class="text-lg font-semibold text-slate-900">
              {{ $t('admin.ai.skillRegistry.title') }}
            </h2>
            <p class="max-w-3xl text-sm leading-6 text-slate-600">
              {{ $t('admin.ai.skillRegistry.pageDesc') }}
            </p>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2 lg:min-w-[420px] lg:grid-cols-4">
          <div class="rounded-2xl bg-slate-50 p-3">
            <div class="text-xs text-slate-500">{{ $t('admin.ai.skillRegistry.total') }}</div>
            <div class="mt-1 text-xl font-semibold text-slate-900">{{ stats.total }}</div>
          </div>
          <div class="rounded-2xl bg-slate-50 p-3">
            <div class="text-xs text-slate-500">{{ $t('admin.ai.skillRegistry.installed') }}</div>
            <div class="mt-1 text-xl font-semibold text-slate-900">{{ stats.installed }}</div>
          </div>
          <div class="rounded-2xl bg-slate-50 p-3">
            <div class="text-xs text-slate-500">{{ $t('admin.ai.skillRegistry.rated') }}</div>
            <div class="mt-1 text-xl font-semibold text-slate-900">{{ stats.rated }}</div>
          </div>
          <div class="rounded-2xl bg-slate-50 p-3">
            <div class="text-xs text-slate-500">{{ $t('admin.plugin.action.upgrade') }}</div>
            <div class="mt-1 text-xl font-semibold text-slate-900">{{ stats.upgradable }}</div>
          </div>
        </div>
      </div>
    </section>

    <section class="rounded-3xl border border-border bg-background p-4 shadow-sm">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
        <Input
          v-model:value="keyword"
          :placeholder="$t('admin.ai.skillRegistry.searchPlaceholder')"
          allow-clear
          class="lg:max-w-sm"
          @press-enter="loadPackages"
        />
        <div class="flex flex-wrap gap-2">
          <Button
            :type="sort === '-downloads' ? 'primary' : 'default'"
            @click="
              sort = '-downloads';
              loadPackages();
            "
          >
            {{ $t('admin.ai.skillRegistry.sortDownloads') }}
          </Button>
          <Button
            :type="sort === '-rating' ? 'primary' : 'default'"
            @click="
              sort = '-rating';
              loadPackages();
            "
          >
            {{ $t('admin.ai.skillRegistry.sortRating') }}
          </Button>
          <Button
            :type="sort === '-updated_at' ? 'primary' : 'default'"
            @click="
              sort = '-updated_at';
              loadPackages();
            "
          >
            {{ $t('admin.ai.skillRegistry.sortUpdated') }}
          </Button>
        </div>
        <Button class="lg:ml-auto" @click="loadPackages">
          {{ $t('admin.common.refresh') }}
        </Button>
        <Button
          v-if="stats.upgradable > 0"
          v-access:code="['plugin_skill_registry:install']"
          type="primary"
          :loading="batchUpgrading"
          @click="batchUpgradePackages"
        >
          {{ $t('admin.ai.skillRegistry.upgradeAll') }}
        </Button>
      </div>
    </section>

    <section class="rounded-3xl border border-border bg-background p-4 shadow-sm">
      <div v-if="loading" class="flex items-center justify-center py-16">
        <Spin />
      </div>
      <div
        v-else-if="packages.length > 0"
        class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
      >
        <Card
          v-for="item in packages"
          :key="item.slug"
          :body-style="{ padding: '18px' }"
          class="h-full rounded-3xl border border-slate-200 transition-shadow hover:shadow-md"
        >
          <div class="flex h-full flex-col gap-4">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="truncate text-base font-semibold text-slate-900">
                  {{ item.display_name || item.name || item.slug }}
                </div>
                <div class="mt-1 text-xs text-slate-500">
                  {{ item.author || $t('admin.ai.skillRegistry.unknownAuthor') }}
                </div>
              </div>
              <Tag v-if="item.is_installed" color="success">
                {{ $t('admin.ai.skillRegistry.installed') }}
              </Tag>
              <Tag v-if="item.can_upgrade" color="processing">
                {{ $t('admin.plugin.action.upgrade') }}
              </Tag>
            </div>

            <p class="min-h-[66px] text-sm leading-6 text-slate-600">
              {{ item.description || $t('admin.ai.skillRegistry.emptyDescription') }}
            </p>

            <div class="flex flex-wrap gap-1.5">
              <Tag v-for="tagItem in item.tags || []" :key="tagItem">
                {{ tagItem }}
              </Tag>
            </div>

            <div class="grid grid-cols-3 gap-2 text-xs text-slate-500">
              <div>
                <div>{{ $t('admin.ai.skillRegistry.version') }}</div>
                <div class="mt-1 font-medium text-slate-900">
                  {{
                    item.can_upgrade
                      ? `${item.installed_version || item.version || '-'} -> ${item.latest_version || '-'}`
                      : item.version || '-'
                  }}
                </div>
              </div>
              <div>
                <div>{{ $t('admin.ai.skillRegistry.downloads') }}</div>
                <div class="mt-1 font-medium text-slate-900">{{ item.downloads || 0 }}</div>
              </div>
              <div>
                <div>{{ $t('admin.ai.skillRegistry.rating') }}</div>
                <div class="mt-1 font-medium text-slate-900">{{ item.rating || '-' }}</div>
              </div>
            </div>

            <div class="mt-auto flex items-center gap-2">
              <Button class="flex-1" @click="openDetail(item)">
                {{ $t('admin.ai.skillRegistry.viewDetail') }}
              </Button>
              <Button
                v-access:code="['plugin_skill_registry:install']"
                type="primary"
                class="flex-1"
                :disabled="Boolean(item.is_installed) && !item.can_upgrade"
                :loading="installingSlug === item.slug || upgradingSlug === item.slug"
                @click="item.can_upgrade ? upgradePackage(item) : installPackage(item)"
              >
                {{
                  item.can_upgrade
                    ? $t('admin.plugin.action.upgrade')
                    : item.is_installed
                      ? $t('admin.ai.skillRegistry.installed')
                      : $t('admin.ai.skillRegistry.install')
                }}
              </Button>
            </div>
          </div>
        </Card>
      </div>
      <Empty v-else :description="$t('admin.ai.skillRegistry.empty')" />
    </section>

    <Modal
      v-model:open="detailOpen"
      :title="activeDetail?.display_name || activeDetail?.name || activeDetail?.slug"
      :footer="null"
      width="880px"
      destroy-on-close
    >
      <div v-if="detailLoading" class="flex items-center justify-center py-16">
        <Spin />
      </div>
      <div v-else-if="activeDetail" class="space-y-4">
        <p class="text-sm leading-6 text-slate-600">
          {{ activeDetail.description || $t('admin.ai.skillRegistry.emptyDescription') }}
        </p>
        <div class="grid gap-3 md:grid-cols-3">
          <div class="rounded-2xl bg-slate-50 p-3">
            <div class="text-xs text-slate-500">{{ $t('admin.ai.skillRegistry.version') }}</div>
            <div class="mt-1 text-sm font-medium text-slate-900">
              {{
                activeDetail.can_upgrade
                  ? `${activeDetail.installed_version || activeDetail.version || '-'} -> ${activeDetail.latest_version || '-'}`
                  : activeDetail.version || '-'
              }}
            </div>
          </div>
          <div class="rounded-2xl bg-slate-50 p-3">
            <div class="text-xs text-slate-500">{{ $t('admin.ai.skillRegistry.downloads') }}</div>
            <div class="mt-1 text-sm font-medium text-slate-900">{{ activeDetail.downloads || 0 }}</div>
          </div>
          <div class="rounded-2xl bg-slate-50 p-3">
            <div class="text-xs text-slate-500">{{ $t('admin.ai.skillRegistry.rating') }}</div>
            <div class="mt-1 text-sm font-medium text-slate-900">{{ activeDetail.rating || '-' }}</div>
          </div>
        </div>
        <pre
          v-if="activeDetail.source_url"
          class="overflow-auto rounded-2xl bg-slate-50 p-3 text-xs text-slate-600"
        >{{ activeDetail.source_url }}</pre>
        <Tag v-if="activeDetail.source_locked" color="processing">
          {{ $t('admin.ai.skillRegistry.sourceLocked') }}
        </Tag>
        <div class="space-y-2">
          <h3 class="text-sm font-semibold text-slate-900">
            {{ $t('admin.ai.skillRegistry.readme') }}
          </h3>
          <pre class="max-h-[320px] overflow-auto rounded-2xl bg-slate-950/95 p-4 text-xs leading-6 text-slate-100">{{ activeDetail.readme || activeDetail.changelog || $t('admin.ai.skillRegistry.noReadme') }}</pre>
        </div>
      </div>
    </Modal>

    <Modal
      v-model:open="batchResultOpen"
      :title="$t('admin.ai.skillRegistry.upgradeResultTitle')"
      :footer="null"
      width="760px"
    >
      <div v-if="batchUpgradeResult" class="space-y-4">
        <div class="grid gap-3 md:grid-cols-3">
          <div class="rounded-2xl bg-slate-50 p-3">
            <div class="text-xs text-slate-500">
              {{ $t('admin.ai.skillRegistry.upgradeRequested') }}
            </div>
            <div class="mt-1 text-sm font-semibold text-slate-900">
              {{ batchUpgradeResult.requested || 0 }}
            </div>
          </div>
          <div class="rounded-2xl bg-emerald-50 p-3">
            <div class="text-xs text-emerald-600">
              {{ $t('admin.ai.skillRegistry.upgradeSucceeded') }}
            </div>
            <div class="mt-1 text-sm font-semibold text-emerald-700">
              {{ batchUpgradeResult.upgraded?.length || 0 }}
            </div>
          </div>
          <div class="rounded-2xl bg-rose-50 p-3">
            <div class="text-xs text-rose-600">
              {{ $t('admin.ai.skillRegistry.upgradeFailed') }}
            </div>
            <div class="mt-1 text-sm font-semibold text-rose-700">
              {{ batchUpgradeResult.failed?.length || 0 }}
            </div>
          </div>
        </div>

        <div
          v-if="(batchUpgradeResult.upgraded || []).length > 0"
          class="space-y-2"
        >
          <h3 class="text-sm font-semibold text-slate-900">
            {{ $t('admin.ai.skillRegistry.upgradeSucceeded') }}
          </h3>
          <div class="space-y-2">
            <div
              v-for="item in batchUpgradeResult.upgraded || []"
              :key="item.registry_slug"
              class="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-3"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate text-sm font-medium text-slate-900">
                    {{ item.package_name || item.registry_slug }}
                  </div>
                  <div class="mt-1 text-xs text-slate-500">
                    {{ item.previous_version || '-' }} ->
                    {{ item.latest_version || '-' }}
                  </div>
                </div>
                <Tag color="success">{{ $t('admin.plugin.action.upgrade') }}</Tag>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="(batchUpgradeResult.failed || []).length > 0"
          class="space-y-2"
        >
          <h3 class="text-sm font-semibold text-slate-900">
            {{ $t('admin.ai.skillRegistry.upgradeFailed') }}
          </h3>
          <div class="space-y-2">
            <div
              v-for="item in batchUpgradeResult.failed || []"
              :key="item.slug"
              class="rounded-2xl border border-rose-100 bg-rose-50/70 p-3"
            >
              <div class="text-sm font-medium text-slate-900">
                {{ item.slug }}
              </div>
              <div
                class="mt-1 whitespace-pre-wrap break-all text-xs leading-5 text-rose-700"
              >
                {{ item.error }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  </div>
</template>
