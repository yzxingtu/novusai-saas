import type { Ref } from 'vue';

import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';

import { computed, nextTick, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { getSkillPackageListApi } from '#/api/admin/skill-packages';

type UseSkillPackagePageOptions = {
  onCreateSkill?: Ref<(() => void) | null>;
};

export function useSkillPackagePage(options: UseSkillPackagePageOptions = {}) {
  const route = useRoute();
  const router = useRouter();

  const packages = ref<AdminSkillPackageInfo[]>([]);
  const packagesLoading = ref(false);
  const searchKeyword = ref('');
  const selectedPackageId = ref<null | number>(null);

  const filteredPackages = computed(() => {
    const keyword = searchKeyword.value.toLowerCase().trim();
    if (!keyword) {
      return packages.value;
    }

    return packages.value.filter(
      (item) =>
        item.name.toLowerCase().includes(keyword) ||
        (item.description && item.description.toLowerCase().includes(keyword)),
    );
  });

  const selectedPackage = computed(
    () =>
      packages.value.find((item) => item.id === selectedPackageId.value) ??
      null,
  );

  function getRoutePackageId(): null | number {
    const raw = route.query.package_id;
    const normalized = Array.isArray(raw) ? raw[0] : raw;
    const value = Number(normalized);
    return Number.isFinite(value) ? value : null;
  }

  async function maybeHandleRouteAction() {
    const action = Array.isArray(route.query.action)
      ? route.query.action[0]
      : route.query.action;
    const openCreateSkill = options.onCreateSkill?.value;

    if (
      action !== 'create_skill' ||
      !selectedPackageId.value ||
      !openCreateSkill
    ) {
      return;
    }

    await nextTick();
    openCreateSkill();

    const { action: _ignored, ...rest } = route.query;
    router.replace({ path: route.path, query: rest });
  }

  async function loadPackages() {
    packagesLoading.value = true;
    try {
      const response = await getSkillPackageListApi({
        'page[size]': 200,
        sort: 'sort_order,-created_at',
      });
      packages.value = response.items;

      const routePackageId = getRoutePackageId();
      if (
        routePackageId !== null &&
        response.items.some((item) => item.id === routePackageId)
      ) {
        selectedPackageId.value = routePackageId;
      } else if (
        selectedPackageId.value === null ||
        !response.items.some((item) => item.id === selectedPackageId.value)
      ) {
        selectedPackageId.value =
          response.items.length > 0 ? (response.items[0]?.id ?? null) : null;
      }

      await maybeHandleRouteAction();
    } catch {
      packages.value = [];
    } finally {
      packagesLoading.value = false;
    }
  }

  function onSelectPackage(pkg: AdminSkillPackageInfo) {
    selectedPackageId.value = pkg.id;
  }

  function updateSearchKeyword(value: string) {
    searchKeyword.value = value;
  }

  onMounted(() => {
    void loadPackages();
  });

  return {
    filteredPackages,
    loadPackages,
    onSelectPackage,
    packagesLoading,
    searchKeyword,
    selectedPackage,
    selectedPackageId,
    updateSearchKeyword,
  };
}
