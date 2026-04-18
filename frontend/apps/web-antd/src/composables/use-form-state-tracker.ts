/**
 * Form State Tracker
 * 表单状态追踪器
 *
 * Provides a global singleton that tracks the open/close state of CRUD forms,
 * current field values, validation errors, and mode (add/edit/view).
 * 提供全局单例，追踪 CRUD 表单的打开/关闭状态、当前字段值、验证错误和模式。
 *
 * Pages auto-register via useCrudDrawer integration;
 * AI operations query state via getFormState(pageKey).
 * 页面通过 useCrudDrawer 集成自动注册；
 * AI 操作通过 getFormState(pageKey) 查询状态。
 *
 * Usage:
 * ```ts
 * // In useCrudDrawer (auto-integrated)
 * formStateTracker.open(pageKey, { mode: 'add', schema: formSchema(false) });
 * formStateTracker.close(pageKey);
 *
 * // In AI operations
 * const state = formStateTracker.getState(pageKey);
 * ```
 */

import type { EnhancedFormFieldDescriptor } from './ai-operation-types';

import type {
  FormFieldDescriptor,
  FormSession,
  FormSessionMode,
} from '#/components/business/ai-runtime/form-session-manager';

import { FormSessionManager } from '#/components/business/ai-runtime/form-session-manager';
import { $t } from '#/locales';

/**
 * Form state snapshot for a page
 * 页面表单状态快照
 */
export interface FormState {
  /** Whether the form is currently open / 表单是否已打开 */
  isOpen: boolean;
  /** Form mode / 表单模式 */
  mode: 'add' | 'edit' | 'view';
  /** Current field values / 当前字段值 */
  currentValues: Record<string, unknown>;
  /** Fields that have been modified from initial values / 已修改的字段 */
  dirtyFields: string[];
  /** Validation errors (fieldName → error message) / 验证错误 */
  validationErrors: Record<string, string>;
  /** Form field schema descriptors / 表单字段 schema 描述 */
  fieldDescriptors: Record<string, EnhancedFormFieldDescriptor>;
}

/** Form API interface matching useCrudDrawer's formApi / 匹配 useCrudDrawer 的 formApi 接口 */
export interface TrackableFormApi {
  getValues: () => Promise<Record<string, unknown>>;
  setValues: (values: Record<string, unknown>) => void;
  validate: () => Promise<
    { errors?: Record<string, unknown>; valid: boolean } | { valid: boolean }
  >;
  /** Optional: programmatic form submit (e.g. trigger drawer onConfirm) / 可选：程序化表单提交 */
  submitForm?: () => Promise<void>;
}

interface TrackerEntry {
  pageKey: string;
  sessionId: string;
  mode: 'add' | 'edit' | 'view';
  formApi: null | TrackableFormApi;
  fieldDescriptors: Record<string, EnhancedFormFieldDescriptor>;
  initialValues: Record<string, unknown>;
}

function mapTrackerModeToSessionMode(
  mode: 'add' | 'edit' | 'view',
): FormSessionMode {
  if (mode === 'add') return 'create';
  return mode;
}

function toRuntimeFieldDescriptors(
  descriptors: Record<string, EnhancedFormFieldDescriptor>,
  initialValues: Record<string, unknown>,
): FormFieldDescriptor[] {
  return Object.entries(descriptors).map(([name, descriptor]) => ({
    name,
    label: descriptor.label ?? name,
    required: !!descriptor.required,
    type: descriptor.component,
    initialValue: initialValues[name],
    value: initialValues[name],
  }));
}

/**
 * Global form state tracker singleton
 * 全局表单状态追踪单例
 */
class FormStateTrackerImpl {
  private _entries = new Map<string, TrackerEntry>();
  private _formSessions = new FormSessionManager();
  private _sessionIdByPageKey = new Map<string, string>();
  private _sessionIdCounter = 0;

  /**
   * Clear all entries (for testing/reset)
   * 清空所有条目
   */
  clear(): void {
    this._entries.clear();
    this._sessionIdByPageKey.clear();
    this._formSessions.clear();
  }

  /**
   * Mark form as closed for a page
   * 标记页面表单为关闭状态
   */
  close(pageKey: string): void {
    const sessionId = this.resolveSessionId(pageKey);
    if (!sessionId) {
      return;
    }
    this.closeBySessionId(sessionId);
  }

  getActiveFieldDescriptors(
    surfaceIdOrPageKey?: string,
  ): FormFieldDescriptor[] {
    return this.getActiveSession(surfaceIdOrPageKey)?.fields ?? [];
  }

  getActiveSession(surfaceIdOrPageKey?: string): FormSession | null {
    if (!surfaceIdOrPageKey) {
      return this._formSessions.getActiveSession();
    }
    const sessionId = this.resolveSessionId(surfaceIdOrPageKey);
    if (sessionId) {
      return this._formSessions.getSession(sessionId);
    }
    return this._formSessions.getActiveSession(surfaceIdOrPageKey);
  }

  getActiveSessionByPageKey(pageKey: string): FormSession | null {
    const sessionId = this._sessionIdByPageKey.get(pageKey);
    if (!sessionId) {
      return null;
    }
    return this._formSessions.getSession(sessionId);
  }

  /**
   * Get the live field descriptors for a page (refreshed each time form opens).
   * Falls back to the only tracked entry if exact key not found.
   * 获取页面的实时字段描述（每次表单打开时刷新）。精确 key 未找到时回退到唯一追踪条目。
   */
  getFieldDescriptors(
    pageKey: string,
  ): null | Record<string, EnhancedFormFieldDescriptor> {
    const exact = this.getEntry(pageKey);
    if (exact) return exact.fieldDescriptors;
    if (this._entries.size === 1) {
      return this.getSingleEntry()?.fieldDescriptors ?? null;
    }
    return null;
  }

  /**
   * Get the FormApi for a page (for fill_form / submit_form).
   * Falls back to the only open entry if the exact pageKey has no match
   * and exactly one form is currently tracked.
   * 获取页面的 FormApi（用于 fill_form / submit_form）。
   * 精确 key 无匹配且仅一个表单被追踪时，回退到该表单。
   */
  getFormApi(pageKey: string): null | TrackableFormApi {
    const exact = this.getEntry(pageKey);
    if (exact) return exact.formApi;

    // Fallback: if only one form is open, it's likely the intended target / 回退：仅一个表单打开时视为目标
    if (this._entries.size === 1) {
      return this.getSingleEntry()?.formApi ?? null;
    }
    return null;
  }

  getSession(pageKey: string): FormSession | null {
    const sessionId = this.resolveSessionId(pageKey);
    if (!sessionId) {
      return null;
    }
    return this._formSessions.getSession(sessionId);
  }

  getSessionId(pageKey: string): null | string {
    return this._sessionIdByPageKey.get(pageKey) ?? null;
  }

  /**
   * Get current form state for a page
   * 获取页面当前表单状态
   */
  async getState(pageKey: string): Promise<FormState> {
    const entry = this.getEntry(pageKey);
    if (!entry) {
      return {
        isOpen: false,
        mode: 'add',
        currentValues: {},
        dirtyFields: [],
        validationErrors: {},
        fieldDescriptors: {},
      };
    }

    let currentValues: Record<string, unknown> = {};
    let validationErrors: Record<string, string> = {};

    if (entry.formApi) {
      try {
        currentValues = await entry.formApi.getValues();
      } catch {
        // Form may not be ready yet / 表单可能尚未就绪
      }

      try {
        const { valid } = await entry.formApi.validate();
        if (!valid) {
          validationErrors = {
            _form: $t('shared.pageOperation.msg.formHasValidationErrors'),
          };
        }
      } catch {
        // Validation may throw if form is not ready / 表单未就绪时 validate 可能抛错
      }
    }

    // Compute dirty fields / 计算脏字段
    const dirtyFields: string[] = [];
    for (const [key, value] of Object.entries(currentValues)) {
      const initial = entry.initialValues[key];
      const match =
        value === initial ||
        ((value === null || value === undefined) &&
          (initial === null || initial === undefined)) ||
        (typeof value === 'object' &&
          typeof initial === 'object' &&
          JSON.stringify(value) === JSON.stringify(initial));
      if (!match) {
        dirtyFields.push(key);
      }
    }

    return {
      isOpen: true,
      mode: entry.mode,
      currentValues,
      dirtyFields,
      validationErrors,
      fieldDescriptors: entry.fieldDescriptors,
    };
  }

  /**
   * Get state with fallback: if exact key not found but exactly one form
   * is tracked, return that form's state.
   * 带回退的表单状态获取：精确 key 未找到但仅一个表单被追踪时返回该表单状态。
   */
  async getStateWithFallback(pageKey: string): Promise<FormState> {
    if (this.resolveSessionId(pageKey)) {
      return this.getState(pageKey);
    }
    if (this._entries.size === 1) {
      const sessionId = this.getSingleSessionId();
      if (sessionId) {
        return this.getState(sessionId);
      }
    }
    return this.getState(pageKey);
  }

  /**
   * Get all tracked page keys (for debugging)
   * 获取所有追踪的页面 key
   */
  getTrackedKeys(): string[] {
    return [...this._sessionIdByPageKey.keys()];
  }

  /**
   * Check if a form is currently open for a page
   * 检查页面是否有表单打开
   */
  isOpen(pageKey: string): boolean {
    return !!this.resolveSessionId(pageKey);
  }

  /**
   * Check form open status with fallback: if exact key not found but
   * exactly one form is tracked, treat it as open.
   * 带回退的表单打开状态检查：精确 key 未找到但仅一个表单被追踪时视为打开。
   */
  isOpenWithFallback(pageKey: string): boolean {
    if (this.resolveSessionId(pageKey)) return true;
    return this._entries.size === 1;
  }

  listSessions(): FormSession[] {
    return this._formSessions.listSessions();
  }

  /**
   * Mark form as open for a page
   * 标记页面表单为打开状态
   */
  open(
    pageKey: string,
    opts: {
      fieldDescriptors?: Record<string, EnhancedFormFieldDescriptor>;
      formApi?: null | TrackableFormApi;
      initialValues?: Record<string, unknown>;
      mode: 'add' | 'edit' | 'view';
    },
  ): string {
    const previousSessionId = this._sessionIdByPageKey.get(pageKey);
    if (previousSessionId) {
      this.closeBySessionId(previousSessionId);
    }

    const sessionId = this.createSessionId(pageKey);
    const fieldDescriptors = opts.fieldDescriptors ?? {};
    const initialValues = opts.initialValues ?? {};
    this._sessionIdByPageKey.set(pageKey, sessionId);
    this._entries.set(sessionId, {
      pageKey,
      sessionId,
      mode: opts.mode,
      formApi: opts.formApi ?? null,
      fieldDescriptors,
      initialValues,
    });

    this._formSessions.upsertSession({
      form_session_id: sessionId,
      surface_id: sessionId,
      mode: mapTrackerModeToSessionMode(opts.mode),
      entity_name: pageKey.split('.').at(-1) ?? undefined,
      fields: toRuntimeFieldDescriptors(fieldDescriptors, initialValues),
      initial_values: initialValues,
      current_values: initialValues,
      submit_policy: 'confirm',
    });
    return sessionId;
  }

  setSessionFieldValues(
    pageKey: string,
    values: Record<string, unknown>,
  ): FormSession | null {
    const sessionId = this.resolveSessionId(pageKey);
    if (!sessionId) {
      return null;
    }
    return this._formSessions.updateFieldValues(sessionId, values);
  }

  private closeBySessionId(sessionId: string): void {
    const entry = this._entries.get(sessionId);
    if (!entry) {
      this._formSessions.closeSession(sessionId);
      return;
    }
    this._entries.delete(sessionId);
    if (this._sessionIdByPageKey.get(entry.pageKey) === sessionId) {
      this._sessionIdByPageKey.delete(entry.pageKey);
    }
    this._formSessions.closeSession(sessionId);
  }

  private createSessionId(pageKey: string): string {
    this._sessionIdCounter += 1;
    const normalizedPageKey = pageKey
      .trim()
      .replaceAll(/[^\w.-]+/g, '-')
      .replaceAll(/-+/g, '-')
      .replaceAll(/^-|-$/g, '');
    const base = normalizedPageKey || 'form';
    return `${base}__session_${Date.now()}_${this._sessionIdCounter}`;
  }

  private getEntry(pageKeyOrSessionId: string): null | TrackerEntry {
    const sessionId = this.resolveSessionId(pageKeyOrSessionId);
    if (!sessionId) {
      return null;
    }
    return this._entries.get(sessionId) ?? null;
  }

  private getSingleEntry(): null | TrackerEntry {
    const firstEntry = this._entries.entries().next().value;
    return firstEntry ? firstEntry[1] : null;
  }

  private getSingleSessionId(): null | string {
    const firstEntry = this._entries.keys().next().value;
    return typeof firstEntry === 'string' ? firstEntry : null;
  }

  private resolveSessionId(pageKeyOrSessionId: string): null | string {
    if (this._entries.has(pageKeyOrSessionId)) {
      return pageKeyOrSessionId;
    }
    return this._sessionIdByPageKey.get(pageKeyOrSessionId) ?? null;
  }
}

/** Global singleton instance / 全局单例 */
export const formStateTracker = new FormStateTrackerImpl();
