// Test type: smoke
// Scope: Playwright SSE capture helpers for real-browser AI chat smoke.
import type { Page } from '@playwright/test';

type JsonRecord = Record<string, unknown>;

/**
 * SSE event parsed from the completed stream body.
 * 从完整 SSE 流内容解析出的事件。
 */
export interface SSEEvent {
  data: string;
  event?: string;
}

/**
 * Parsed AI chat SSE done payload.
 * AI 聊天 SSE done 事件载荷。
 */
export interface SSEDonePayload {
  completion_reason?: null | string;
  context_compacted: boolean;
  conversation_id: number;
  duration_ms: number;
  memory_flush_triggered?: boolean;
  memory_recalled: boolean;
  prune_stats?: JsonRecord | null;
  rag_source_kinds: string[];
  selected_skill_names?: string[];
  selected_tool_names?: string[];
  termination_reason?: null | string;
  total_tokens: number;
  trace_id?: null | string;
}

/**
 * tool_start event shape.
 * tool_start 事件结构。
 */
export interface ToolStartEvent {
  arguments: JsonRecord;
  id: null | string;
  name: string;
  package_name: null | string;
  skill_name: null | string;
}

/**
 * Audited tool call entry merged with the matching tool_start arguments when available.
 * 审计后的工具调用条目，尽量与对应的 tool_start 参数合并。
 */
export interface ToolCallAudit {
  arguments: JsonRecord | null;
  duration_ms: number;
  error: null | string;
  error_type: null | string;
  name: string;
  output: null | string;
  package_name: null | string;
  skill_name: null | string;
  success: boolean;
  summary: null | string;
  summary_payload: unknown;
}

/**
 * Consent request event captured from the stream.
 * 流中的 consent 请求事件。
 */
export interface ToolConsentRequest {
  arguments: JsonRecord;
  name: string;
  package_name: null | string;
  skill_name: null | string;
}

/**
 * Confirmation request event captured from the stream.
 * 流中的确认请求事件。
 */
export interface ConfirmationRequest {
  action: string;
  preview: unknown;
  table: null | string;
}

/**
 * Tool optimization event emitted before execution.
 * 工具优化事件。
 */
export interface OptimizingToolsEvent {
  execution_path: null | string;
  selected: number;
  total: number;
}

interface CapturedChatStream {
  body: string;
  contentType: string;
  done: boolean;
  error: null | string;
  lastUpdatedAt: number;
  requestAt: number;
  responseAt: number;
  url: string;
}

/**
 * Aggregate metrics for one AI chat turn collected from the SSE response body.
 * 从 SSE 响应体收集的一轮 AI 对话指标。
 */
export interface ChatTurnMetrics {
  actionButtons: JsonRecord[];
  completionReason: null | string;
  confirmationRequests: ConfirmationRequest[];
  contentType: string;
  conversationId: null | number;
  donePayload: null | SSEDonePayload;
  errors: string[];
  events: SSEEvent[];
  executionPath: null | string;
  fullResponse: string;
  isTrueStream: boolean;
  optimizingTools: null | OptimizingToolsEvent;
  redundantSteps: string[];
  selectedSkillNames: string[];
  toolCalls: ToolCallAudit[];
  toolConsentRequests: ToolConsentRequest[];
  toolStarts: ToolStartEvent[];
  totalMs: number;
  traceId: null | string;
  ttfb: number;
  ttft: number;
}

function isJsonRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function filterJsonRecord(value: unknown): value is JsonRecord {
  return isJsonRecord(value);
}

function readBoolean(value: unknown, fallback = false) {
  return typeof value === 'boolean' ? value : fallback;
}

function readNumber(value: unknown, fallback = 0) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function readString(value: unknown): null | string {
  return typeof value === 'string' && value.trim() ? value : null;
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean);
}

function readRecord(value: unknown): JsonRecord {
  return isJsonRecord(value) ? value : {};
}

function parseSSEEvents(raw: string): SSEEvent[] {
  const events: SSEEvent[] = [];

  for (const block of raw.split('\n\n')) {
    const trimmed = block.trim();
    if (!trimmed) continue;

    const lines = trimmed.split('\n');
    const dataLines: string[] = [];
    let event: string | undefined;

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        event = line.slice(7);
        continue;
      }

      if (line.startsWith('data: ')) {
        dataLines.push(line.slice(6));
      }
    }

    if (dataLines.length === 0) continue;

    events.push({
      data: dataLines.join('\n'),
      event,
    });
  }

  return events;
}

function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  message: string,
) {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(message));
    }, timeoutMs);

    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

function detectRedundantSteps(toolCalls: ToolCallAudit[]) {
  const redundant: string[] = [];
  const seen = new Set<string>();

  for (const toolCall of toolCalls) {
    const normalizedArgs = JSON.stringify(toolCall.arguments ?? {});
    const key = `${toolCall.name}:${normalizedArgs}`;

    if (seen.has(key)) {
      redundant.push(`REDUNDANT:${toolCall.name}`);
    } else {
      seen.add(key);
    }
  }

  return redundant;
}

function normalizeDomTranscriptText(value: string) {
  return value.replaceAll(/\s+/g, ' ').trim();
}

function normalizeDonePayload(payload: JsonRecord): SSEDonePayload {
  return {
    completion_reason: readString(payload.completion_reason) ?? null,
    context_compacted: readBoolean(payload.context_compacted),
    conversation_id: readNumber(payload.conversation_id),
    duration_ms: readNumber(payload.duration_ms),
    memory_flush_triggered:
      typeof payload.memory_flush_triggered === 'boolean'
        ? payload.memory_flush_triggered
        : undefined,
    memory_recalled: readBoolean(payload.memory_recalled),
    prune_stats: isJsonRecord(payload.prune_stats) ? payload.prune_stats : null,
    rag_source_kinds: readStringArray(payload.rag_source_kinds),
    selected_skill_names: readStringArray(payload.selected_skill_names),
    selected_tool_names: readStringArray(payload.selected_tool_names),
    termination_reason: readString(payload.termination_reason) ?? null,
    total_tokens: readNumber(payload.total_tokens),
    trace_id: readString(payload.trace_id) ?? null,
  };
}

function resolveApiPrefixFromPath(pathname: string) {
  if (pathname.startsWith('/admin')) {
    return '/admin';
  }
  if (
    pathname === '/' ||
    pathname.startsWith('/agents') ||
    pathname.startsWith('/ai-chat') ||
    pathname.startsWith('/api/user') ||
    pathname.startsWith('/help') ||
    pathname.startsWith('/settings') ||
    pathname.startsWith('/user')
  ) {
    return '/api/user';
  }
  return '/tenant';
}

function resolveApiPrefixFromRequestUrl(requestUrl: string) {
  const pathname = new URL(requestUrl, 'http://localhost').pathname;
  if (pathname.includes('/api/user/')) {
    return '/api/user';
  }
  if (pathname.includes('/admin/')) {
    return '/admin';
  }
  if (pathname.includes('/tenant/')) {
    return '/tenant';
  }
  return null;
}

async function fetchPersistedConversationSnapshot(
  page: Page,
  conversationId: number,
  streamUrl?: string,
  suffix = '',
) {
  const pageUrl = new URL(page.url());
  const apiPrefix =
    (streamUrl ? resolveApiPrefixFromRequestUrl(streamUrl) : null) ??
    resolveApiPrefixFromPath(pageUrl.pathname);
  const response = await page
    .context()
    .request.get(
      `${pageUrl.origin}${apiPrefix}/ai/agent-chat/conversations/${conversationId}${suffix}`,
    );
  if (!response.ok()) {
    return null;
  }
  const payload = (await response.json().catch(() => null)) as unknown;
  if (!isJsonRecord(payload)) {
    return null;
  }
  const normalized = readRecord(payload.data);
  if (Object.keys(normalized).length > 0) {
    return normalized;
  }
  return payload;
}

function mergeToolCallWithStart(
  payload: JsonRecord,
  pendingStarts: Map<string, ToolStartEvent[]>,
) {
  const name =
    readString(payload.name) ??
    readString(readRecord(payload.function).name) ??
    'unknown_tool';
  const queue = pendingStarts.get(name);
  const startEvent = queue?.shift() ?? null;

  return {
    arguments: startEvent?.arguments ?? readRecord(payload.arguments),
    duration_ms: readNumber(payload.duration_ms),
    error: readString(payload.error),
    error_type: readString(payload.error_type),
    name,
    output: readString(payload.output),
    package_name:
      startEvent?.package_name ?? readString(payload.package_name) ?? null,
    skill_name:
      startEvent?.skill_name ?? readString(payload.skill_name) ?? null,
    success:
      typeof payload.success === 'boolean'
        ? payload.success
        : Boolean(payload.output),
    summary: readString(payload.summary),
    summary_payload: payload.summary_payload,
  } satisfies ToolCallAudit;
}

function readCanonicalEvidenceName(evidence: JsonRecord) {
  return (
    readString(evidence.tool_name) ??
    readString(evidence.toolName) ??
    readString(evidence.source_ref) ??
    readString(evidence.sourceRef) ??
    readString(evidence.display_name) ??
    readString(evidence.displayName) ??
    readString(evidence.title)
  );
}

function appendCanonicalToolEvidence(
  toolCalls: ToolCallAudit[],
  evidence: unknown,
) {
  if (!isJsonRecord(evidence)) {
    return;
  }
  if (readString(evidence.kind) !== 'tool') {
    return;
  }
  const name = readCanonicalEvidenceName(evidence);
  if (!name) {
    return;
  }

  const argumentsValue = isJsonRecord(evidence.arguments)
    ? evidence.arguments
    : null;
  const status = readString(evidence.status);
  const error = readString(evidence.error);
  const output = readString(evidence.output);
  const summary =
    readString(evidence.snippet) ??
    readString(evidence.summary) ??
    readString(evidence.title);
  const summaryPayload =
    evidence.summary_payload ?? evidence.summaryPayload ?? null;
  const evidenceId =
    readString(evidence.tool_call_id) ??
    readString(evidence.toolCallId) ??
    readString(evidence.id);
  const key = [
    evidenceId ? `id:${evidenceId}` : 'shape',
    name,
    JSON.stringify(argumentsValue ?? {}),
    output ?? summary ?? error ?? '',
  ].join('\u001F');
  const existingKey = (toolCall: ToolCallAudit) =>
    [
      toolCall.summary_payload &&
      isJsonRecord(toolCall.summary_payload) &&
      readString(toolCall.summary_payload.evidence_id)
        ? `id:${readString((toolCall.summary_payload as JsonRecord).evidence_id)}`
        : 'shape',
      toolCall.name,
      JSON.stringify(toolCall.arguments ?? {}),
      toolCall.output ?? toolCall.summary ?? toolCall.error ?? '',
    ].join('\u001F');
  if (toolCalls.some((toolCall) => existingKey(toolCall) === key)) {
    return;
  }

  toolCalls.push({
    arguments: argumentsValue,
    duration_ms: readNumber(evidence.duration_ms ?? evidence.durationMs),
    error,
    error_type: readString(evidence.error_type ?? evidence.errorType),
    name,
    output,
    package_name: null,
    skill_name: readString(evidence.skill_name ?? evidence.skillName),
    success: status ? status === 'success' : !error,
    summary,
    summary_payload: isJsonRecord(summaryPayload)
      ? {
          ...summaryPayload,
          ...(evidenceId ? { evidence_id: evidenceId } : {}),
        }
      : evidenceId
        ? { evidence_id: evidenceId }
        : summaryPayload,
  });
}

function appendCanonicalToolEvidenceList(
  toolCalls: ToolCallAudit[],
  value: unknown,
) {
  if (!Array.isArray(value)) {
    return;
  }
  for (const item of value) {
    appendCanonicalToolEvidence(toolCalls, item);
  }
}

function appendCanonicalToolEvidenceFromTurnFlow(
  toolCalls: ToolCallAudit[],
  value: unknown,
) {
  if (!isJsonRecord(value)) {
    return;
  }
  appendCanonicalToolEvidenceList(toolCalls, value.evidence);
  appendCanonicalToolEvidenceList(toolCalls, value.sources);
}

function appendCanonicalToolEvidenceFromPayload(
  toolCalls: ToolCallAudit[],
  payload: JsonRecord,
) {
  const evidence = payload.evidence;
  if (Array.isArray(evidence)) {
    appendCanonicalToolEvidenceList(toolCalls, evidence);
  } else {
    appendCanonicalToolEvidence(toolCalls, evidence ?? payload);
  }

  appendCanonicalToolEvidenceList(toolCalls, payload.evidences);
  appendCanonicalToolEvidenceList(toolCalls, payload.evidence_items);
  appendCanonicalToolEvidenceFromTurnFlow(
    toolCalls,
    payload.turn_flow ?? payload.turnFlow,
  );

  const turnRecord = readRecord(payload.turn_record ?? payload.turnRecord);
  appendCanonicalToolEvidenceFromTurnFlow(
    toolCalls,
    turnRecord.turn_flow ?? turnRecord.turnFlow,
  );
  const turnRecordMetadata = readRecord(turnRecord.metadata);
  appendCanonicalToolEvidenceFromTurnFlow(
    toolCalls,
    turnRecordMetadata.turn_flow ?? turnRecordMetadata.turnFlow,
  );
}

function appendNestedCanonicalToolEvidenceFromPayload(
  toolCalls: ToolCallAudit[],
  payload: JsonRecord,
) {
  const evidence = payload.evidence;
  if (Array.isArray(evidence)) {
    appendCanonicalToolEvidenceList(toolCalls, evidence);
  } else {
    appendCanonicalToolEvidence(toolCalls, evidence);
  }

  appendCanonicalToolEvidenceList(toolCalls, payload.evidences);
  appendCanonicalToolEvidenceList(toolCalls, payload.evidence_items);
  appendCanonicalToolEvidenceFromTurnFlow(
    toolCalls,
    payload.turn_flow ?? payload.turnFlow,
  );
}

function appendCanonicalToolEvidenceFromEventPayload(
  toolCalls: ToolCallAudit[],
  payload: JsonRecord,
  payloadEvent: null | string,
) {
  if (payloadEvent === 'turn_evidence' || payloadEvent === 'turn_flow') {
    appendCanonicalToolEvidenceFromPayload(toolCalls, payload);
    return true;
  }
  if (payloadEvent === 'turn_stage' || payloadEvent === 'turn_stage_update') {
    appendNestedCanonicalToolEvidenceFromPayload(toolCalls, payload);
    return true;
  }
  return false;
}

/**
 * 中文: Test type: smoke. 仅从 canonical turn-flow 证据提取 smoke 工具指标。
 * EN: Test type: smoke. Extract smoke tool metrics only from canonical turn-flow evidence.
 *
 * 中文: Mock strategy: 不 mock LLM 或工具执行器，调用方传入已捕获的 SSE 事件。
 * EN: Mock strategy: no LLM/tool mocks; callers provide captured SSE events.
 */
export function collectCanonicalToolCallsFromEvents(events: SSEEvent[]) {
  const toolCalls: ToolCallAudit[] = [];
  for (const event of events) {
    if (event.data === '[DONE]') continue;
    let payload: JsonRecord;
    try {
      const parsed = JSON.parse(event.data) as unknown;
      if (!isJsonRecord(parsed)) {
        continue;
      }
      payload = parsed;
    } catch {
      continue;
    }
    const payloadEvent = readString(payload.event) ?? event.event ?? null;
    if (payloadEvent === 'done') {
      appendCanonicalToolEvidenceFromPayload(toolCalls, payload);
    } else {
      appendCanonicalToolEvidenceFromEventPayload(
        toolCalls,
        payload,
        payloadEvent,
      );
    }
  }
  return toolCalls;
}

function installChatStreamCapture() {
  const globalWindow = window as typeof globalThis &
    Window & {
      __aiChatStreamCaptureInstalled?: boolean;
      __aiChatStreamRecords?: CapturedChatStream[];
    };
  const captureContainsTerminalEvent = (body: string) => {
    if (!body) {
      return false;
    }
    if (body.includes('data: [DONE]')) {
      return true;
    }

    const blocks = body.split('\n\n');
    for (const block of blocks) {
      const trimmed = block.trim();
      if (!trimmed || !trimmed.includes('data: ')) {
        continue;
      }
      const dataLine = trimmed
        .split('\n')
        .find((line) => line.startsWith('data: '));
      if (!dataLine) {
        continue;
      }
      const payload = dataLine.slice(6);
      if (payload === '[DONE]') {
        return true;
      }
      try {
        const parsed = JSON.parse(payload) as { event?: string };
        if (parsed?.event === 'done') {
          return true;
        }
      } catch {
        // Ignore incomplete JSON fragments while the stream is still growing.
      }
    }

    return false;
  };

  if (globalWindow.__aiChatStreamCaptureInstalled) {
    return;
  }

  globalWindow.__aiChatStreamCaptureInstalled = true;
  globalWindow.__aiChatStreamRecords ??= [];

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const input = args[0];
    const init = args[1];
    const request =
      typeof Request !== 'undefined' && input instanceof Request ? input : null;
    const url =
      typeof input === 'string'
        ? input
        : request?.url || String((input as { url?: string })?.url || '');
    const method = (init?.method || request?.method || 'GET').toUpperCase();
    const requestAt = Date.now();
    const response = await originalFetch(...args);

    if (method === 'POST' && /\/chat\/stream(?:\?|$)/.test(url)) {
      const record: CapturedChatStream = {
        body: '',
        contentType: response.headers.get('content-type') || '',
        done: false,
        error: null,
        lastUpdatedAt: Date.now(),
        requestAt,
        responseAt: Date.now(),
        url,
      };
      globalWindow.__aiChatStreamRecords?.push(record);

      const clonedResponse = response.clone();
      const streamReader = clonedResponse.body?.getReader();

      if (streamReader) {
        const decoder = new TextDecoder();
        (async () => {
          try {
            while (true) {
              const { done, value } = await streamReader.read();
              if (done) {
                record.body += decoder.decode();
                record.lastUpdatedAt = Date.now();
                record.done = true;
                return;
              }
              record.body += decoder.decode(value, { stream: true });
              record.lastUpdatedAt = Date.now();
              if (captureContainsTerminalEvent(record.body)) {
                record.done = true;
                await streamReader.cancel().catch(() => undefined);
                return;
              }
            }
          } catch (error: unknown) {
            record.error =
              error instanceof Error ? error.message : String(error);
            record.lastUpdatedAt = Date.now();
            record.done = true;
          }
        })();
      } else {
        clonedResponse
          .text()
          .then((body) => {
            record.body = body;
            record.lastUpdatedAt = Date.now();
            record.done = true;
          })
          .catch((error: unknown) => {
            record.error =
              error instanceof Error ? error.message : String(error);
            record.lastUpdatedAt = Date.now();
            record.done = true;
          });
      }
    }

    return response;
  };
}

async function ensureChatStreamCapture(page: Page) {
  await page.addInitScript(installChatStreamCapture);
  await page.evaluate(installChatStreamCapture).catch(() => undefined);
}

async function readChatStreamCount(page: Page) {
  return page
    .evaluate(() => {
      const globalWindow = window as typeof globalThis &
        Window & {
          __aiChatStreamRecords?: CapturedChatStream[];
        };
      return globalWindow.__aiChatStreamRecords?.length ?? 0;
    })
    .catch(() => 0);
}

/**
 * Set up SSE capture for one chat turn.
 * 为单轮聊天建立 SSE 抓取。
 */
export async function interceptChatSSE(
  page: Page,
): Promise<(options?: { timeout?: number }) => Promise<ChatTurnMetrics>> {
  await ensureChatStreamCapture(page);
  const streamIndex = await readChatStreamCount(page);

  return async (
    options: { timeout?: number } = {},
  ): Promise<ChatTurnMetrics> => {
    const timeout = options.timeout ?? 120_000;
    const capture = await withTimeout(
      page
        .waitForFunction(
          (index) => {
            const globalWindow = window as typeof globalThis &
              Window & {
                __aiChatStreamRecords?: CapturedChatStream[];
              };
            const record = globalWindow.__aiChatStreamRecords?.[index];
            if (!record) {
              return null;
            }
            if (record.done || record.error) {
              return record;
            }
            return null;
          },
          streamIndex,
          { timeout },
        )
        .then(async () => {
          return page.evaluate((index) => {
            const globalWindow = window as typeof globalThis &
              Window & {
                __aiChatStreamRecords?: CapturedChatStream[];
              };
            return globalWindow.__aiChatStreamRecords?.[index] ?? null;
          }, streamIndex);
        }),
      timeout,
      'Timed out waiting for AI chat SSE response body.',
    );

    if (!capture) {
      throw new Error('Timed out waiting for AI chat SSE capture.');
    }

    const contentType = capture.contentType || '';
    const requestAt = capture.requestAt || Date.now();
    const responseAt = capture.responseAt || Date.now();
    const rawBody = capture.body || '';
    const finishedAt = Date.now();
    const events = parseSSEEvents(rawBody);

    let conversationId: null | number = null;
    let fullResponse = '';
    let donePayload: null | SSEDonePayload = null;
    let executionPath: null | string = null;
    let optimizingTools: null | OptimizingToolsEvent = null;
    let traceId: null | string = null;
    let completionReason: null | string = null;

    const errors: string[] = [];
    const actionButtons: JsonRecord[] = [];
    const toolStarts: ToolStartEvent[] = [];
    const toolCalls: ToolCallAudit[] = [];
    const toolConsentRequests: ToolConsentRequest[] = [];
    const confirmationRequests: ConfirmationRequest[] = [];
    const selectedSkillNames = new Set<string>();
    const pendingStarts = new Map<string, ToolStartEvent[]>();

    if (capture.error) {
      errors.push(capture.error);
    }

    let messageEventCount = 0;

    for (const event of events) {
      if (event.data === '[DONE]') continue;

      let payload: JsonRecord;
      try {
        const parsed = JSON.parse(event.data) as unknown;
        if (!isJsonRecord(parsed)) {
          errors.push(`unparseable: ${event.data.slice(0, 100)}`);
          continue;
        }
        payload = parsed;
      } catch {
        errors.push(`unparseable: ${event.data.slice(0, 100)}`);
        continue;
      }

      const payloadEvent = readString(payload.event) ?? event.event ?? null;
      const payloadTraceId = readString(payload.trace_id);
      if (payloadTraceId) {
        traceId = payloadTraceId;
      }

      for (const skillName of readStringArray(payload.selected_skill_names)) {
        selectedSkillNames.add(skillName);
      }

      const maybeCompletionReason =
        readString(payload.completion_reason) ??
        readString(payload.termination_reason);
      if (maybeCompletionReason) {
        completionReason = maybeCompletionReason;
      }

      if (payloadEvent === 'conversation') {
        conversationId = readNumber(
          payload.conversation_id,
          conversationId ?? 0,
        );
        if (conversationId === 0) {
          conversationId = null;
        }
        continue;
      }

      if (payloadEvent === 'optimizing_tools') {
        optimizingTools = {
          execution_path: readString(payload.execution_path),
          selected: readNumber(payload.selected),
          total: readNumber(payload.total),
        };
        executionPath = optimizingTools.execution_path;
        continue;
      }

      if (payloadEvent === 'message') {
        fullResponse += readString(payload.delta) ?? '';
        messageEventCount += 1;
        continue;
      }

      if (payloadEvent === 'tool_start') {
        const startEvent: ToolStartEvent = {
          arguments: readRecord(payload.arguments),
          id: readString(payload.id),
          name:
            readString(payload.name) ??
            readString(readRecord(payload.function).name) ??
            'unknown_tool',
          package_name: readString(payload.package_name),
          skill_name: readString(payload.skill_name),
        };
        toolStarts.push(startEvent);
        const startQueue = pendingStarts.get(startEvent.name) ?? [];
        startQueue.push(startEvent);
        pendingStarts.set(startEvent.name, startQueue);
        continue;
      }

      if (payloadEvent === 'tool_call') {
        mergeToolCallWithStart(payload, pendingStarts);
        continue;
      }

      if (payloadEvent === 'tool_consent_request') {
        toolConsentRequests.push({
          arguments: readRecord(payload.arguments),
          name: readString(payload.name) ?? 'unknown_tool',
          package_name: readString(payload.package_name),
          skill_name: readString(payload.skill_name),
        });
        continue;
      }

      if (payloadEvent === 'confirmation_request') {
        confirmationRequests.push({
          action: readString(payload.action) ?? '',
          preview: payload.preview,
          table: readString(payload.table),
        });
        continue;
      }

      if (payloadEvent === 'action_buttons') {
        if (Array.isArray(payload.buttons)) {
          for (const button of payload.buttons) {
            if (isJsonRecord(button)) {
              actionButtons.push(button);
            }
          }
        }
        continue;
      }

      if (
        appendCanonicalToolEvidenceFromEventPayload(
          toolCalls,
          payload,
          payloadEvent,
        )
      ) {
        continue;
      }

      if (payloadEvent === 'done') {
        donePayload = normalizeDonePayload(payload);
        conversationId = donePayload.conversation_id || conversationId;
        traceId = donePayload.trace_id ?? traceId;
        for (const skillName of donePayload.selected_skill_names ?? []) {
          selectedSkillNames.add(skillName);
        }
        completionReason =
          donePayload.completion_reason ??
          donePayload.termination_reason ??
          completionReason;
        appendCanonicalToolEvidenceFromPayload(toolCalls, payload);
        continue;
      }

      if (payloadEvent === 'error') {
        errors.push(
          readString(payload.message) ??
            readString(payload.error) ??
            JSON.stringify(payload),
        );
      }
    }

    const ttfb = Math.max(0, responseAt - requestAt);
    const ttft = messageEventCount > 0 ? ttfb : 0;
    const totalMs = Math.max(0, finishedAt - requestAt);
    if (conversationId && conversationId > 0) {
      const persistedSnapshot = await fetchPersistedConversationSnapshot(
        page,
        conversationId,
        capture.url,
      ).catch(() => null);
      const persistedMessages = Array.isArray(persistedSnapshot?.message_list)
        ? persistedSnapshot.message_list.filter((item) =>
            filterJsonRecord(item),
          )
        : [];
      for (
        let messageIndex = persistedMessages.length - 1;
        messageIndex >= 0;
        messageIndex -= 1
      ) {
        const persistedMessage = persistedMessages[messageIndex];
        if (!persistedMessage) {
          continue;
        }
        if (readString(persistedMessage.role) !== 'assistant') {
          continue;
        }
        const metadata = readRecord(persistedMessage.metadata);
        const turnRecord = readRecord(metadata.turn_record);
        appendCanonicalToolEvidenceFromPayload(toolCalls, persistedMessage);
        appendCanonicalToolEvidenceFromPayload(
          toolCalls,
          readRecord(persistedMessage.turn_record),
        );
        appendCanonicalToolEvidenceFromPayload(toolCalls, metadata);
        appendCanonicalToolEvidenceFromPayload(toolCalls, turnRecord);
        if (!fullResponse.trim()) {
          const persistedContent = readString(persistedMessage.content);
          if (persistedContent) {
            fullResponse = persistedContent;
          }
        }
        break;
      }
      if (toolCalls.length === 0) {
        const timelineSnapshot = await fetchPersistedConversationSnapshot(
          page,
          conversationId,
          capture.url,
          '/timeline',
        ).catch(() => null);
        let timelineItems: JsonRecord[] = [];
        if (Array.isArray(timelineSnapshot)) {
          timelineItems = timelineSnapshot.filter((item) =>
            filterJsonRecord(item),
          );
        } else if (Array.isArray(timelineSnapshot?.items)) {
          timelineItems = timelineSnapshot.items.filter((item) =>
            filterJsonRecord(item),
          );
        }
        for (const item of timelineItems) {
          appendNestedCanonicalToolEvidenceFromPayload(toolCalls, item);
        }
      }
    }
    if (!fullResponse.trim()) {
      const domFallback = await page
        .evaluate(() => {
          const panel = document.querySelector(
            '[data-testid="ai-chat-slide-panel"]',
          );
          if (!panel) {
            return '';
          }
          const surfaces = [
            ...panel.querySelectorAll('.assistant-message-surface'),
          ];
          for (let index = surfaces.length - 1; index >= 0; index -= 1) {
            const surface = surfaces[index] as HTMLElement | undefined;
            if (!surface) {
              continue;
            }
            const contentCandidates = [
              surface.querySelector(
                '.assistant-message-body .assistant-content-block .markdown-render',
              ),
              surface.querySelector(
                '.assistant-message-body .assistant-content-block',
              ),
              surface.querySelector('.assistant-message-body'),
              surface.querySelector('.assistant-message-top'),
            ];
            for (const candidate of contentCandidates) {
              const text = candidate?.textContent?.trim() ?? '';
              if (text) {
                return text;
              }
            }
          }
          return '';
        })
        .catch(() => '');
      if (domFallback.trim()) {
        fullResponse = normalizeDomTranscriptText(domFallback);
      }
    }

    return {
      actionButtons,
      completionReason,
      confirmationRequests,
      contentType,
      conversationId,
      donePayload,
      errors,
      events,
      executionPath,
      fullResponse,
      isTrueStream: messageEventCount >= 3,
      optimizingTools,
      redundantSteps: detectRedundantSteps(toolCalls),
      selectedSkillNames: [...selectedSkillNames],
      toolCalls,
      toolConsentRequests,
      toolStarts,
      totalMs,
      traceId,
      ttfb,
      ttft,
    };
  };
}
