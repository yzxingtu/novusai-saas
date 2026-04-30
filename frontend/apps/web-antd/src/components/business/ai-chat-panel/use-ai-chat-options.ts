import type { Ref } from 'vue';

export interface UseAIChatOptions {
  /** API prefix: '/admin', '/tenant', or '/api/user' / API 前缀 */
  apiPrefix: Ref<string> | string;
  /** Upload endpoint / 上传接口地址 */
  uploadUrl: Ref<string> | string;
  /** Initial agent ID to auto-select after loading agents / 加载后默认选中的智能体 ID */
  initialAgentId?: number | Ref<number | undefined>;
  /** Initial conversation ID to auto-load after agent is selected / 选中智能体后默认加载的对话 ID */
  initialConversationId?: number | Ref<number | undefined>;
  /** Callback when a tool call completes successfully / 工具调用成功回调 */
  onToolCall?: (toolName: string, output: string) => void;
  /** Callback when streaming completes (used for unread badge) / 流式结束回调（未读角标等） */
  onStreamComplete?: () => void;
  /** Callback when required input variables are missing — opens the vars modal / 必填变量缺失时回调，打开变量弹窗 */
  onVariablesMissing?: () => void;
}
