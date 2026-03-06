export { default as AIChatSlidePanel } from './AIChatSlidePanel.vue';
export {
  clearPageContextRegistry,
  getRegisteredKeys,
  registerPageContext,
  resolvePageContext,
} from './page-context-registry';
export type { PageContextData, PageContextResolver } from './page-context-registry';
export {
  clearPageOperationRegistry,
  executePageOperation,
  findPageOperation,
  getRegisteredOperationKeys,
  listPageOperations,
  registerPageOperations,
} from './page-operation-registry';
export type {
  PageOperation,
  PageOperationHandler,
  PageOperationResult,
} from './page-operation-registry';
export { ROUTED_BY, useAgentRouter } from './use-agent-router';
export type { RouteResult, UseAgentRouterOptions } from './use-agent-router';
