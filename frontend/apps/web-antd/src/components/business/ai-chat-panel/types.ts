/**
 * Backward-compatible re-export shim.
 * / 向后兼容 re-export 过渡层。
 */

import type {
  TurnContextSourcePayload,
  TurnRecordPayload,
} from '#/api/shared/types';
import type {
  TurnFlowAnswerCard as BaseTurnFlowAnswerCard,
  TurnFlowAnswerCardSection as BaseTurnFlowAnswerCardSection,
  TurnFlowEvidenceItem as BaseTurnFlowEvidenceItem,
  TurnFlowEvidenceKind as BaseTurnFlowEvidenceKind,
  TurnFlowStage as BaseTurnFlowStage,
  TurnFlowStageStatus as BaseTurnFlowStageStatus,
  TurnFlowStageType as BaseTurnFlowStageType,
  TurnFlowViewModel as BaseTurnFlowViewModel,
  TurnFlowViewPayload as BaseTurnFlowViewPayload,
} from '#/types/ai-chat';

export type TurnFlowStageType = BaseTurnFlowStageType;
export type TurnFlowStageStatus = BaseTurnFlowStageStatus;
export type TurnFlowStage = BaseTurnFlowStage;
export type TurnEvidenceKind = BaseTurnFlowEvidenceKind;
export type TurnEvidenceItem = BaseTurnFlowEvidenceItem;
export type TurnAnswerCardSection = BaseTurnFlowAnswerCardSection;
export type TurnAnswerCard = BaseTurnFlowAnswerCard;
export type TurnFlowViewModel = BaseTurnFlowViewModel;

export interface DisplayReferenceLink {
  hostLabel: string;
  href: string;
  id: string;
  kind: 'reference' | TurnEvidenceKind;
  label: string;
  snippet?: string;
  source: 'content' | 'turn_flow';
}

export interface PreparedMessageContent {
  bodyMarkdown: string;
  references: DisplayReferenceLink[];
  suppressed: boolean;
}

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
    /** Unified turn-flow read model for timeline/evidence rendering / 统一 turn-flow 读模型 */
    turnFlow?: BaseTurnFlowViewPayload;
    /** Turn-level diagnostics: termination reason / 轮次诊断：终止原因 */
    terminationReason?: string;
    /** Turn-level diagnostics: turn outcome / 轮次诊断：轮次结果 */
    turnOutcome?: string;
  }
}

export * from '#/types/ai-chat';
