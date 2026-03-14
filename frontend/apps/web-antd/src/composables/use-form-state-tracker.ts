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

import type { EnhancedFormFieldDescriptor } from './use-ai-operations';

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
  validate: () => Promise<{ valid: boolean }>;
}

interface TrackerEntry {
  mode: 'add' | 'edit' | 'view';
  formApi: TrackableFormApi | null;
  fieldDescriptors: Record<string, EnhancedFormFieldDescriptor>;
  initialValues: Record<string, unknown>;
}

/**
 * Global form state tracker singleton
 * 全局表单状态追踪单例
 */
class FormStateTrackerImpl {
  private _entries = new Map<string, TrackerEntry>();

  /**
   * Mark form as open for a page
   * 标记页面表单为打开状态
   */
  open(
    pageKey: string,
    opts: {
      mode: 'add' | 'edit' | 'view';
      formApi?: TrackableFormApi | null;
      fieldDescriptors?: Record<string, EnhancedFormFieldDescriptor>;
      initialValues?: Record<string, unknown>;
    },
  ): void {
    this._entries.set(pageKey, {
      mode: opts.mode,
      formApi: opts.formApi ?? null,
      fieldDescriptors: opts.fieldDescriptors ?? {},
      initialValues: opts.initialValues ?? {},
    });
  }

  /**
   * Mark form as closed for a page
   * 标记页面表单为关闭状态
   */
  close(pageKey: string): void {
    this._entries.delete(pageKey);
  }

  /**
   * Check if a form is currently open for a page
   * 检查页面是否有表单打开
   */
  isOpen(pageKey: string): boolean {
    return this._entries.has(pageKey);
  }

  /**
   * Get current form state for a page
   * 获取页面当前表单状态
   */
  async getState(pageKey: string): Promise<FormState> {
    const entry = this._entries.get(pageKey);
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
          validationErrors = { _form: 'Form has validation errors / 表单存在验证错误' };
        }
      } catch {
        // Validation may throw if form is not ready
      }
    }

    // Compute dirty fields / 计算脏字段
    const dirtyFields: string[] = [];
    for (const [key, value] of Object.entries(currentValues)) {
      const initial = entry.initialValues[key];
      const match = value === initial
        || (value == null && initial == null)
        || (typeof value === 'object' && typeof initial === 'object'
          && JSON.stringify(value) === JSON.stringify(initial));
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
   * Get the FormApi for a page (for fill_form / submit_form).
   * Falls back to the only open entry if the exact pageKey has no match
   * and exactly one form is currently tracked (handles _aiPageKey mismatch).
   * 获取页面的 FormApi（用于 fill_form / submit_form）。
   * 精确 key 无匹配且仅一个表单被追踪时，回退到该表单（处理 _aiPageKey 不匹配）。
   */
  getFormApi(pageKey: string): TrackableFormApi | null {
    const exact = this._entries.get(pageKey);
    if (exact) return exact.formApi;

    // Fallback: if only one form is open, it's likely the intended target / 回退：仅一个表单打开时视为目标
    if (this._entries.size === 1) {
      const [, entry] = [...this._entries.entries()][0]!;
      return entry.formApi;
    }
    return null;
  }

  /**
   * Check form open status with fallback: if exact key not found but
   * exactly one form is tracked, treat it as open (handles _aiPageKey mismatch).
   * 带回退的表单打开状态检查：精确 key 未找到但仅一个表单被追踪时视为打开。
   */
  isOpenWithFallback(pageKey: string): boolean {
    if (this._entries.has(pageKey)) return true;
    return this._entries.size === 1;
  }

  /**
   * Get state with fallback: if exact key not found but exactly one form
   * is tracked, return that form's state (handles _aiPageKey mismatch).
   * 带回退的表单状态获取：精确 key 未找到但仅一个表单被追踪时返回该表单状态。
   */
  async getStateWithFallback(pageKey: string): Promise<FormState> {
    if (this._entries.has(pageKey)) {
      return this.getState(pageKey);
    }
    if (this._entries.size === 1) {
      const [actualKey] = [...this._entries.keys()];
      return this.getState(actualKey!);
    }
    return this.getState(pageKey);
  }

  /**
   * Get the live field descriptors for a page (refreshed each time form opens).
   * Falls back to the only tracked entry if exact key not found.
   * 获取页面的实时字段描述（每次表单打开时刷新）。精确 key 未找到时回退到唯一追踪条目。
   */
  getFieldDescriptors(pageKey: string): Record<string, EnhancedFormFieldDescriptor> | null {
    const exact = this._entries.get(pageKey);
    if (exact) return exact.fieldDescriptors;
    if (this._entries.size === 1) {
      const [, entry] = [...this._entries.entries()][0]!;
      return entry.fieldDescriptors;
    }
    return null;
  }

  /**
   * Get all tracked page keys (for debugging)
   * 获取所有追踪的页面 key
   */
  getTrackedKeys(): string[] {
    return [...this._entries.keys()];
  }

  /**
   * Clear all entries (for testing/reset)
   * 清空所有条目
   */
  clear(): void {
    this._entries.clear();
  }
}

/** Global singleton instance / 全局单例 */
export const formStateTracker = new FormStateTrackerImpl();
