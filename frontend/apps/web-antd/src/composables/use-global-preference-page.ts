/**
 * Shared composable for global preference pages (Admin & Tenant) / 全局偏好页共享 Composable
 * Provides loading, saving, live preview, and revert-on-leave logic.
 *
 * Live preview: form changes are applied to Vben in real-time.
 * If the user leaves without saving, Vben reverts to the snapshot taken on load.
 */
import type { PreferencesData } from '#/api/shared/types';

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';
import {
  applyPreferencesToVben,
  getVbenSnapshot,
  useUserPreferenceStore,
} from '#/store/shared/user-preference';
import { showRequestError } from '#/utils/error-helpers';

type Side = 'admin' | 'tenant';

export function useGlobalPreferencePage(side: Side) {
  const preferenceStore = useUserPreferenceStore();

  const formData = ref<PreferencesData>({});
  const loading = ref(false);
  const saving = ref(false);
  const loaded = ref(false);
  const savedFormSnapshot = ref('');

  let vbenSnapshot: PreferencesData = {};

  function serializePreferences(data: PreferencesData) {
    return JSON.stringify(data);
  }

  async function loadData() {
    loading.value = true;
    try {
      const data = await preferenceStore.loadGlobalPreferences(side);
      if (data) {
        formData.value = { ...data };
      }
      savedFormSnapshot.value = serializePreferences(formData.value);
    } catch (error) {
      showRequestError(error, 'common.preference.loadFailed');
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
        savedFormSnapshot.value = serializePreferences(formData.value);
        vbenSnapshot = getVbenSnapshot();
        message.success($t('common.preference.saveSuccess'));
      } else {
        message.error($t('common.preference.saveFailed'));
      }
    } catch (error) {
      showRequestError(error, 'common.preference.saveFailed');
    } finally {
      saving.value = false;
    }
  }

  function applyPreview(data: PreferencesData) {
    preferenceStore.setGlobalPreviewPreferences(data);
    void applyPreferencesToVben(data).catch((error) => {
      console.warn(
        '[GlobalPreferencePage] Failed to apply preview preferences:',
        error,
      );
    });
  }

  function revertToSnapshot() {
    applyPreview(vbenSnapshot);
  }

  const isDirty = computed(() => {
    if (!loaded.value) {
      return false;
    }
    return serializePreferences(formData.value) !== savedFormSnapshot.value;
  });

  watch(
    formData,
    (val) => {
      if (!loaded.value) return;
      applyPreview(val);
    },
    { deep: true },
  );

  onMounted(async () => {
    vbenSnapshot = getVbenSnapshot();
    preferenceStore.globalPreviewActive = true;
    preferenceStore.setGlobalPreviewPreferences(null);
    await loadData();
    loaded.value = true;
  });

  onBeforeUnmount(() => {
    revertToSnapshot();
    preferenceStore.setGlobalPreviewPreferences(null);
    preferenceStore.globalPreviewActive = false;
  });

  return {
    formData,
    isDirty,
    loading,
    saving,
    loadData,
    onSave,
  };
}
