<script setup lang="ts">
import { SUPPORT_LANGUAGES } from '@vben/constants';
import { $t } from '@vben/locales';

import InputItem from '../input-item.vue';
import SelectItem from '../select-item.vue';
import SwitchItem from '../switch-item.vue';

defineOptions({
  name: 'PreferenceGeneralConfig',
});

withDefaults(defineProps<{ showWatermark?: boolean }>(), {
  showWatermark: true,
});

const appLocale = defineModel<string>('appLocale');
const appDynamicTitle = defineModel<boolean>('appDynamicTitle');
const appWatermark = defineModel<boolean>('appWatermark');
const appWatermarkContent = defineModel<string>('appWatermarkContent');
const appEnableCheckUpdates = defineModel<boolean>('appEnableCheckUpdates');
const appPlainTextInputAiEnabled = defineModel<boolean>(
  'appPlainTextInputAiEnabled',
);
</script>

<template>
  <SelectItem v-model="appLocale" :items="SUPPORT_LANGUAGES">
    {{ $t('preferences.language') }}
  </SelectItem>
  <SwitchItem v-model="appDynamicTitle">
    {{ $t('preferences.dynamicTitle') }}
  </SwitchItem>
  <template v-if="showWatermark">
    <SwitchItem
      v-model="appWatermark"
      @update:model-value="
        (val) => {
          if (!val) appWatermarkContent = '';
        }
      "
    >
      {{ $t('preferences.watermark') }}
    </SwitchItem>
    <InputItem
      v-if="appWatermark"
      v-model="appWatermarkContent"
      :placeholder="$t('preferences.watermarkContent')"
    >
      {{ $t('preferences.watermarkContent') }}
    </InputItem>
  </template>
  <SwitchItem v-model="appEnableCheckUpdates">
    {{ $t('preferences.checkUpdates') }}
  </SwitchItem>
  <SwitchItem
    v-model="appPlainTextInputAiEnabled"
    :tip="$t('preferences.ai.plainTextInputAssistTip')"
  >
    {{ $t('preferences.ai.plainTextInputAssist') }}
  </SwitchItem>
</template>
