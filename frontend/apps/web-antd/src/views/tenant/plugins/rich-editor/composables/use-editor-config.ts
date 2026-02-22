/**
 * useEditorConfig 组合式函数
 *
 * 调用 GET /tenant/plugins/rich-editor/config 获取插件配置（AI/协作开关状态）
 * 缓存到响应式状态，供编辑器各组件条件渲染使用
 */
import { ref } from 'vue';

import { requestClient } from '#/utils/request';

/** 插件配置类型 */
export interface RichEditorPluginConfig {
  ai_enabled: boolean;
  collaboration_enabled: boolean;
  auto_save_interval: number;
  max_document_size_mb: number;
  max_collaborators: number;
  max_versions: number;
  theme: string;
}

/** 默认配置（所有功能关闭） */
const DEFAULT_CONFIG: RichEditorPluginConfig = {
  ai_enabled: false,
  collaboration_enabled: false,
  auto_save_interval: 30,
  max_document_size_mb: 10,
  max_collaborators: 10,
  max_versions: 50,
  theme: 'default',
};

export function useEditorConfig() {
  const config = ref<RichEditorPluginConfig>({ ...DEFAULT_CONFIG });
  const configLoading = ref(false);
  const configLoaded = ref(false);

  /** 加载插件配置 */
  async function loadConfig(): Promise<RichEditorPluginConfig> {
    if (configLoaded.value) return config.value;

    configLoading.value = true;
    try {
      const res = await requestClient.get<RichEditorPluginConfig>(
        '/tenant/plugins/rich-editor/config',
      );
      config.value = { ...DEFAULT_CONFIG, ...res };
      configLoaded.value = true;
    } catch {
      // 加载失败使用默认配置（所有功能关闭）
      config.value = { ...DEFAULT_CONFIG };
      configLoaded.value = true;
    } finally {
      configLoading.value = false;
    }
    return config.value;
  }

  /** AI 是否启用 */
  const aiEnabled = ref(false);
  /** 协作是否启用 */
  const collaborationEnabled = ref(false);

  /** 加载并解析开关状态 */
  async function init(): Promise<void> {
    const cfg = await loadConfig();
    aiEnabled.value = cfg.ai_enabled;
    collaborationEnabled.value = cfg.collaboration_enabled;
  }

  return {
    config,
    configLoading,
    configLoaded,
    aiEnabled,
    collaborationEnabled,
    loadConfig,
    init,
  };
}
