import type { LocatorCandidate } from './locator-resolver';
import type {
  UIActionDiff,
  UIActionExecutionResult,
  UIActionExecutorOptions,
  UIActionInvokePayload,
  UIStateSnapshot,
} from './ui-action-executor-contracts';

import { tAiRuntime, tAiRuntimeSurfaceKind } from './i18n';
import { LocatorResolutionError, LocatorResolver } from './locator-resolver';
import { getCurrentRouteSecurityPolicy } from './runtime-bridge-core';
import { evaluateAIActionSecurity } from './security-policy';
import {
  buildDiff,
  DEFAULT_WAIT_TIMEOUT_MS,
  defaultPageKeyResolver,
  shouldForceChanged,
  snapshotUIState,
} from './ui-action-executor-support';

export type {
  UIActionDiff,
  UIActionExecutionResult,
  UIActionExecutorOptions,
  UIActionInvokePayload,
  UIActionType,
  UISurfaceKind,
  UISurfaceSummary,
} from './ui-action-executor-contracts';

export class UIActionExecutor {
  private readonly getPageKey: () => string;
  private readonly getUiEpoch: () => number;
  private readonly locatorResolver: LocatorResolver;
  private readonly setUiEpoch: (value: number) => void;

  constructor(options: UIActionExecutorOptions = {}) {
    let localUiEpoch = 0;
    this.getUiEpoch = options.getUiEpoch ?? (() => localUiEpoch);
    this.setUiEpoch =
      options.setUiEpoch ??
      ((value) => {
        localUiEpoch = value;
      });
    this.getPageKey = options.getPageKey ?? defaultPageKeyResolver;
    this.locatorResolver =
      options.locatorResolver ?? new LocatorResolver(options.locatorOptions);
  }

  async execute(
    action: UIActionInvokePayload,
  ): Promise<UIActionExecutionResult> {
    const before = this.snapshot();
    try {
      if (action.action_type === 'ui_click') {
        return await this.executeClick(action, before);
      }
      if (action.action_type === 'ui_open_surface') {
        return await this.executeOpenSurface(action, before);
      }
      return {
        diff: this.buildDiff(before, before, false),
        error: tAiRuntime('unsupportedActionType', {
          actionType: action.action_type,
        }),
        error_type: 'invalid_action_type',
        message: tAiRuntime('unsupportedActionType', {
          actionType: action.action_type,
        }),
        success: false,
      };
    } catch (error) {
      if (error instanceof LocatorResolutionError) {
        return {
          data:
            error.candidates.length > 0
              ? { candidates: error.candidates }
              : undefined,
          diff: this.buildDiff(before, this.snapshot(), false),
          error: error.message,
          error_type: error.code,
          message: error.message,
          success: false,
        };
      }
      const message = error instanceof Error ? error.message : String(error);
      return {
        diff: this.buildDiff(before, this.snapshot(), false),
        error: message,
        error_type: 'internal_error',
        message,
        success: false,
      };
    }
  }

  private buildDiff(
    before: UIStateSnapshot,
    after: UIStateSnapshot,
    semanticChanged: boolean,
  ): UIActionDiff {
    return buildDiff({
      after,
      before,
      semanticChanged,
      setUiEpoch: this.setUiEpoch,
    });
  }

  private clickElement(element: HTMLElement): void {
    const clickTarget = element.matches('.ant-pagination-item')
      ? (element.querySelector('a,button') as HTMLElement | null) || element
      : element;
    clickTarget.click();
  }

  private async executeClick(
    action: UIActionInvokePayload,
    before: UIStateSnapshot,
  ): Promise<UIActionExecutionResult> {
    const locator = String(action.target_locator || '')
      .replaceAll(/\s+/g, ' ')
      .trim();
    if (!locator) {
      const message = tAiRuntime('uiClickRequiresTargetLocator');
      return {
        diff: this.buildDiff(before, before, false),
        error: message,
        error_type: 'invalid_input',
        message,
        success: false,
      };
    }

    const resolved = this.locatorResolver.resolve(locator);
    if (resolved.candidate.disabled) {
      const target = resolved.candidate.label || locator;
      const message = tAiRuntime('targetDisabled', { target });
      return {
        data: { candidates: [resolved.candidate] satisfies LocatorCandidate[] },
        diff: this.buildDiff(before, before, false),
        error: message,
        error_type: 'element_disabled',
        message,
        success: false,
      };
    }

    const security = evaluateAIActionSecurity({
      actionKind: 'ui_click',
      element: resolved.element,
      routePolicy: getCurrentRouteSecurityPolicy(),
    });
    if (!security.allowed) {
      const target = resolved.candidate.label || locator;
      const message = tAiRuntime('targetBlockedByPolicy', { target });
      return {
        diff: this.buildDiff(before, before, false),
        error: message,
        error_type: security.reason || 'policy_blocked',
        message,
        success: false,
      };
    }
    if (security.requireConfirm && !action.confirm) {
      const target = resolved.candidate.label || locator;
      const message = tAiRuntime('targetRequiresConfirmation', { target });
      return {
        diff: this.buildDiff(before, before, false),
        error: message,
        error_type: 'confirmation_required',
        message,
        success: false,
      };
    }

    this.clickElement(resolved.element);
    await this.waitForUI(action.wait_timeout_ms);
    const after = this.snapshot();
    const diff = this.buildDiff(
      before,
      after,
      shouldForceChanged(resolved.candidate.kind),
    );

    return {
      data: {
        target_kind: resolved.candidate.kind,
        target_locator: resolved.candidate.locator,
      },
      diff,
      message: resolved.candidate.label
        ? tAiRuntime('clickedTarget', { target: resolved.candidate.label })
        : tAiRuntime('clickActionExecuted'),
      success: true,
    };
  }

  private async executeOpenSurface(
    action: UIActionInvokePayload,
    before: UIStateSnapshot,
  ): Promise<UIActionExecutionResult> {
    const surface = action.surface || {};
    const requestedKind = surface.kind;
    let locator = String(surface.locator || action.target_locator || '')
      .replaceAll(/\s+/g, ' ')
      .trim();

    if (!locator && surface.title) {
      locator = `text:${surface.title}`;
    }
    if (!locator) {
      const message = tAiRuntime('uiOpenSurfaceRequiresLocator');
      return {
        diff: this.buildDiff(before, before, false),
        error: message,
        error_type: 'invalid_input',
        message,
        success: false,
      };
    }

    const resolved = this.locatorResolver.resolve(locator);
    if (resolved.candidate.disabled) {
      const target = resolved.candidate.label || locator;
      const message = tAiRuntime('targetDisabled', { target });
      return {
        diff: this.buildDiff(before, before, false),
        error: message,
        error_type: 'element_disabled',
        message,
        success: false,
      };
    }

    const security = evaluateAIActionSecurity({
      actionKind: 'ui_open_surface',
      element: resolved.element,
      routePolicy: getCurrentRouteSecurityPolicy(),
    });
    if (!security.allowed) {
      const target = resolved.candidate.label || locator;
      const message = tAiRuntime('targetBlockedByPolicy', { target });
      return {
        diff: this.buildDiff(before, before, false),
        error: message,
        error_type: security.reason || 'policy_blocked',
        message,
        success: false,
      };
    }
    if (security.requireConfirm && !action.confirm) {
      const target = resolved.candidate.label || locator;
      const message = tAiRuntime('targetRequiresConfirmation', { target });
      return {
        diff: this.buildDiff(before, before, false),
        error: message,
        error_type: 'confirmation_required',
        message,
        success: false,
      };
    }

    this.clickElement(resolved.element);
    const waitTimeout = Math.max(action.wait_timeout_ms ?? 600, 120);
    await this.waitForUI(waitTimeout);
    const after = this.snapshot();
    const diff = this.buildDiff(before, after, true);

    const added = diff.surfaces_added;
    const kindMatched = requestedKind
      ? added.some((item) => item.kind === requestedKind)
      : added.length > 0;
    if (!kindMatched) {
      const message = requestedKind
        ? tAiRuntime('noNewRequestedSurfaceDetected', {
            kind: tAiRuntimeSurfaceKind(requestedKind),
            locator,
          })
        : tAiRuntime('noNewSurfaceDetected', { locator });
      return {
        diff,
        error: message,
        error_type: 'surface_not_opened',
        message,
        success: false,
      };
    }

    return {
      data: {
        opened_surface_ids: added.map((item) => item.surface_id),
      },
      diff,
      message: tAiRuntime('surfaceOpenedSuccessfully'),
      success: true,
    };
  }

  private snapshot() {
    return snapshotUIState({
      getPageKey: this.getPageKey,
      getUiEpoch: this.getUiEpoch,
    });
  }

  private async waitForUI(timeoutMs = DEFAULT_WAIT_TIMEOUT_MS): Promise<void> {
    const wait = Math.max(timeoutMs, 16);
    await new Promise<void>((resolve) => {
      window.setTimeout(() => resolve(), wait);
    });
  }
}
