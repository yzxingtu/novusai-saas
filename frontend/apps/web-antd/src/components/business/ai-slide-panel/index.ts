export { default as AgentVarsModal } from './AgentVarsModal.vue';
export { default as AIChatComposer } from './AIChatComposer.vue';
export { default as AIChatConversationFooter } from './AIChatConversationFooter.vue';
export { default as AIChatHistoryPane } from './AIChatHistoryPane.vue';
export { default as AIChatMessageViewport } from './AIChatMessageViewport.vue';
export { default as AIChatPanelHeader } from './AIChatPanelHeader.vue';
export { default as AIChatSlidePanel } from './AIChatSlidePanel.vue';
export {
  clearPageContextRegistry,
  getRegisteredKeys,
  pageContextVersion,
  registerPageContext,
  registerPageContextExtras,
  resolvePageContext,
} from './page-context-registry';
export type {
  PageContextData,
  PageContextResolver,
} from './page-context-registry';
export { normalizePageKey } from './page-key-utils';
export {
  appendPageOperations,
  clearPageOperationRegistry,
  executePageOperation,
  findPageOperation,
  getRegisteredOperationKeys,
  listPageOperations,
  pageOperationVersion,
  registerPageOperations,
} from './page-operation-registry';
export type {
  PageOperation,
  PageOperationHandler,
  PageOperationResult,
} from './page-operation-types';
export { default as PageAIRail } from './PageAIRail.vue';
export { ROUTED_BY, useAgentRouter } from './use-agent-router';
export type { RouteResult, UseAgentRouterOptions } from './use-agent-router';
