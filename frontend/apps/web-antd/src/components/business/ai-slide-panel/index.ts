export { default as AIChatSlidePanel } from './AIChatSlidePanel.vue';
export {
  clearPageContextRegistry,
  getRegisteredKeys,
  pageContextVersion,
  registerPageContext,
  resolvePageContext,
} from './page-context-registry';
export type { PageContextData, PageContextResolver } from './page-context-registry';
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
} from './page-operation-registry';
export { normalizePageKey } from './page-key-utils';
export { ROUTED_BY, useAgentRouter } from './use-agent-router';
export type { RouteResult, UseAgentRouterOptions } from './use-agent-router';
