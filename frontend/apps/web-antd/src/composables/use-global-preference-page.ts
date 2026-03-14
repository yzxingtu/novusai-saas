/**
 * Shared composable for global preference pages (Admin & Tenant).
 * Provides loading, saving, live preview, and revert-on-leave logic.
 *
 * Live preview: form changes are applied to Vben in real-time.
 * If the user leaves without saving, Vben reverts to the snapshot taken on load.
 */
import type { PreferencesData } from '#/api/shared/types';

import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { updatePreferences } from '@vben/preferences';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';
import {
  getVbenSnapshot,
  mapToVbenPreferences,
  useUserPreferenceStore,
} from '#/store/shared/user-preference';

type Side = 'admin' | 'tenant';

export function useGlobalPreferencePage(side: Side) {
  const preferenceStore = useUserPreferenceStore();

  const formData = ref<PreferencesData>({});
  const loading = ref(false);
  const saving = ref(false);

  let vbenSnapshot: PreferencesData = {};
  let loaded = false;

  async function loadData() {
    loading.value = true;
    try {
      const data = await preferenceStore.loadGlobalPreferences(side);
      if (data) {
        formData.value = { ...data };
      }
    } catch {
      message.error($t('common.preference.loadFailed'));
    } finally {
      loading.value = false;
    }
  }

  async function onSave() {
    saving.value = true;
    try {
      const result = await preferenceStore.updateGlobalPreferences(
        side,
        formData.value,
      );
      if (result) {
        formData.value = { ...result };
        vbenSnapshot = getVbenSnapshot();
        message.success($t('common.preference.saveSuccess'));
      } else {
        message.error($t('common.preference.saveFailed'));
      }
    } catch {
      message.error($t('common.preference.saveFailed'));
    } finally {
      saving.value = false;
    }
  }

  function applyPreview(data: PreferencesData) {
    const mapped = mapToVbenPreferences(data);
    if (Object.keys(mapped).length > 0) {
      updatePreferences(mapped as Parameters<typeof updatePreferences>[0]);
    }
  }

  function revertToSnapshot() {
    applyPreview(vbenSnapshot);
  }

  watch(
    formData,
    (val) => {
      if (!loaded) return;
      applyPreview(val);
    },
    { deep: true },
  );

  onMounted(async () => {
    vbenSnapshot = getVbenSnapshot();
    preferenceStore.globalPreviewActive = true;
    await loadData();
    loaded = true;
  });

  onBeforeUnmount(() => {
    revertToSnapshot();
    preferenceStore.globalPreviewActive = false;
  });

  return {
    formData,
    loading,
    saving,
    loadData,
    onSave,
  };
}
