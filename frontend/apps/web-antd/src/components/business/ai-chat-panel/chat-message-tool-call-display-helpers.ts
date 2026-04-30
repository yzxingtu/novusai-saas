import type { ToolDisplayItem } from './tool-call-utils';
import type { ToolCallEvent } from './types';

import {
  getSearchSummary,
  getStructuredToolOutput,
  getToolHeadlineSummary,
  getToolTargetBadges,
  hasToolCardDetails,
} from './tool-call-utils';

export interface ToolGroupSummary {
  error: number;
  running: number;
  success: number;
  total: number;
}

export function getToolDisplayState(
  tc: Pick<ToolCallEvent, 'id' | 'name' | 'status'>,
): 'executing' | 'waiting_confirm' {
  if (tc.status !== 'running') return 'executing';
  return 'executing';
}

export function shouldToolExpandByDefault(
  tc: Pick<ToolCallEvent, 'status'>,
): boolean {
  return tc.status === 'running' || tc.status === 'error';
}

export function buildToolDisplayItems(
  toolCalls: ToolCallEvent[],
  options: {
    resolveExpanded: (
      tc: Pick<ToolCallEvent, 'status' | 'summaryPayload'>,
      idx: number,
    ) => boolean;
  },
): ToolDisplayItem[] {
  return toolCalls.map((tc, idx) => {
    const structuredOutput = getStructuredToolOutput(tc);
    const searchSummary = getSearchSummary(tc);
    return {
      index: idx,
      tc,
      hasDetails: hasToolCardDetails(tc),
      expanded: options.resolveExpanded(tc, idx),
      headlineSummary: getToolHeadlineSummary(tc),
      searchSummary,
      structuredOutput,
      targetBadges: getToolTargetBadges(tc),
    };
  });
}

export function getToolGroupSummary(
  tools: ToolCallEvent[],
): null | ToolGroupSummary {
  if (!tools.length) return null;
  const success = tools.filter((tc) => tc.status === 'success').length;
  const error = tools.filter((tc) => tc.status === 'error').length;
  const running = tools.filter((tc) => tc.status === 'running').length;
  return {
    error,
    running,
    success,
    total: tools.length,
  };
}
