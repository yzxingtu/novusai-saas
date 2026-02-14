/**
 * AI Translation — 通过 CRUD Agent 触发 i18n 翻译
 *
 * 架构合规: 所有 AI 交互统一走 Agent 对话引擎 (crud_generator_assistant)
 * 不新建独立 API 端点。
 *
 * 流程:
 * 1. Step 5 打开时自动触发
 * 2. 发送翻译指令给 CRUD Agent
 * 3. Agent 调用 crud_translate_i18n Tool
 * 4. SSE 推送翻译结果
 * 5. 自动填入 I18nPreview
 */

import { ref } from 'vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';

const T = 'admin.dev.crudGenerator';

export interface TranslationResult {
  locale: string;
  translations: Record<string, string>;
}

/**
 * useAiTranslate — AI 翻译 composable
 *
 * @param sendMessage - 发送消息给 CRUD Agent 的函数 (来自 useCrudAiAssistant)
 */
export function useAiTranslate(
  sendMessage?: (message: string) => Promise<void>,
) {
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
   * 触发 AI 翻译
   * 通过 CRUD Agent 发送翻译指令
   */
  async function translate(
    config: CrudConfig,
    targetLocales: string[] = ['en-US'],
  ) {
    if (!sendMessage) {
      translationError.value = 'AI assistant not available';
      return;
    }

    isTranslating.value = true;
    translationError.value = null;
    translationResults.value = [];

    try {
      const zhKeys = extractI18nKeys(config);
      const keysJson = JSON.stringify(zhKeys, null, 2);
      const localesStr = targetLocales.join(', ');

      const prompt = [
        `请将以下中文 i18n JSON 翻译为 ${localesStr}。`,
        `模块名: ${config.module}`,
        `中文 JSON:`,
        '```json',
        keysJson,
        '```',
        `请直接返回翻译后的 JSON，key 保持不变。`,
      ].join('\n');

      await sendMessage(prompt);

      // Translation results will be received via SSE tool_call events
      // and applied by the parent component through the AI assistant integration
    } catch (err) {
      translationError.value = String(err);
    } finally {
      isTranslating.value = false;
    }
  }

  /**
   * 手动设置翻译结果 (从 Agent SSE 回调中调用)
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
