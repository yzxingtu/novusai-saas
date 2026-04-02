/**
 * Backward-compatible re-export shim.
 * / 向后兼容 re-export 过渡层。
 */

import type {
  TurnContextSourcePayload,
  TurnRecordPayload,
} from '#/api/shared/types';

declare module '#/types/ai-chat' {
  interface ChatMessage {
    /** Turn-level diagnostics: context source list / 轮次诊断：上下文来源列表 */
    contextSources?: TurnContextSourcePayload[];
    /** Runtime turn record payload (replay diagnostics) / 运行时轮次记录（回放诊断） */
    turnRecord?: TurnRecordPayload;
    /** Turn-level diagnostics: protocol path / 轮次诊断：协议路径 */
    protocolPath?: string;
    /** Turn-level diagnostics: selected skills / 轮次诊断：被选技能 */
    selectedSkillNames?: string[];
    /** Turn-level diagnostics: selected tools / 轮次诊断：被选工具 */
    selectedToolNames?: string[];
    /** Turn-level diagnostics: termination reason / 轮次诊断：终止原因 */
    terminationReason?: string;
    /** Turn-level diagnostics: turn outcome / 轮次诊断：轮次结果 */
    turnOutcome?: string;
  }
}

export * from '#/types/ai-chat';
