/**
 * AI Translation — 通过全局 AI Chat 触发 i18n 翻译
 *
 * 流程:
 * 1. 调用 translate() 构建翻译提示并复制到剪贴板
 * 2. 自动打开全局 AI Chat Drawer
 * 3. 用户粘贴发送，AI 返回翻译结果
 * 4. 手动通过 setTranslationResult 填入结果
 */

import { ref } from 'vue';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';
import { useGlobalAIChatStore } from '#/store';

import type { CrudConfig } from '../types';

const T = 'admin.dev.crudGenerator';

export interface TranslationResult {
  locale: string;
  translations: Record<string, string>;
}

/**
 * useAiTranslate — AI 翻译 composable
 *
 * 通过全局 AI Chat 发送翻译请求
 */
export function useAiTranslate() {
  const isTranslating = ref(false);
  const translationResults = ref<TranslationResult[]>([]);
  const translationError = ref<string | null>(null);

  /**
   * 从 CrudConfig 提取需要翻译的中文 i18n keys
   */
  function extractI18nKeys(config: CrudConfig): Record<string, string> {
    const keys: Record<string, string> = {};
    const module = config.module || 'module';

    keys[`${module}.title`] = config.display_name || config.module;
    keys[`${module}.createTitle`] = $t(`${T}.translate.createTitle`, { name: config.display_name || '' });
    keys[`${module}.editTitle`] = $t(`${T}.translate.editTitle`, { name: config.display_name || '' });

    for (const field of config.fields) {
      keys[`${module}.field.${field.name}`] = field.label_zh || field.name;
    }

    for (const enumDef of config.enums) {
      for (const val of enumDef.values) {
        keys[`${module}.enum.${enumDef.name}.${val.value}`] = val.label_zh;
      }
    }

    keys[`${module}.search.placeholder`] = $t(`${T}.translate.searchPlaceholder`);
    keys[`${module}.message.createSuccess`] = $t(`${T}.translate.createSuccess`);
    keys[`${module}.message.updateSuccess`] = $t(`${T}.translate.updateSuccess`);
    keys[`${module}.message.deleteSuccess`] = $t(`${T}.translate.deleteSuccess`);
    keys[`${module}.message.deleteConfirm`] = $t(`${T}.translate.deleteConfirm`);

    return keys;
  }

  /**
   * 构建翻译提示、复制到剪贴板并打开全局 AI Chat
   */
  async function translate(
    config: CrudConfig,
    targetLocales: string[] = ['en-US'],
  ) {
    isTranslating.value = true;
    translationError.value = null;
    translationResults.value = [];

    try {
      const zhKeys = extractI18nKeys(config);
      const keysJson = JSON.stringify(zhKeys, null, 2);
      const localesStr = targetLocales.join(', ');

      const prompt = [
        $t(`${T}.translate.promptTranslateTo`, { locales: localesStr }),
        $t(`${T}.translate.promptModuleName`, { module: config.module }),
        $t(`${T}.translate.promptZhJson`),
        '```json',
        keysJson,
        '```',
        $t(`${T}.translate.promptReturnJson`),
      ].join('\n');

      await navigator.clipboard.writeText(prompt);
      message.success($t(`${T}.translate.copiedToClipboard`));

      const globalChat = useGlobalAIChatStore();
      globalChat.show();
    } catch (err) {
      translationError.value = String(err);
    } finally {
      isTranslating.value = false;
    }
  }

  /**
   * 手动设置翻译结果 (从外部回调中调用)
   */
  function setTranslationResult(locale: string, translations: Record<string, string>) {
    const existing = translationResults.value.findIndex((r) => r.locale === locale);
    if (existing >= 0) {
      translationResults.value[existing] = { locale, translations };
    } else {
      translationResults.value.push({ locale, translations });
    }
  }

  /**
   * 获取某语种的翻译结果
   */
  function getTranslation(locale: string): Record<string, string> | null {
    const result = translationResults.value.find((r) => r.locale === locale);
    return result?.translations ?? null;
  }

  return {
    isTranslating,
    translationResults,
    translationError,
    extractI18nKeys,
    translate,
    setTranslationResult,
    getTranslation,
  };
}
