import { describe, expect, it } from 'vitest';

import {
  FormSessionManager,
  inferFormMode,
} from '../form-session-manager';
import { createAntdFormSessionInput } from '../component-adapters/antd-form';
import { createVbenFormSessionInput } from '../component-adapters/vben-form';

describe('form-session-manager', () => {
  it('infers create mode from URL first', () => {
    expect(
      inferFormMode({
        current_url: '/admin/ai/agents/create',
        current_values: { id: 99 },
        record_id: 99,
      }),
    ).toBe('create');
  });

  it('infers edit mode from record_id when URL has no mode hint', () => {
    expect(
      inferFormMode({
        current_url: '/admin/ai/agents',
        record_id: 42,
      }),
    ).toBe('edit');
  });

  it('tracks remaining required fields incrementally', () => {
    const manager = new FormSessionManager();
    const session = manager.upsertSession({
      surface_id: 'drawer:agent-form',
      current_url: '/admin/ai/agents/create',
      fields: [
        { name: 'name', required: true, value: '', initialValue: '' },
        { name: 'description', value: '', initialValue: '' },
        { name: 'model', required: true, value: '', initialValue: '' },
      ],
      submit_policy: 'confirm',
    });

    expect(session.mode).toBe('create');
    expect(session.remaining_required_fields).toEqual(['model', 'name']);
    expect(session.can_submit).toBe(false);

    const partiallyFilled = manager.updateFieldValues(session.form_session_id, {
      name: 'Agent A',
    });
    expect(partiallyFilled?.remaining_required_fields).toEqual(['model']);
    expect(partiallyFilled?.stage).toBe('filled_partial');

    const readyToSubmit = manager.updateFieldValues(session.form_session_id, {
      model: 'gpt-5',
    });
    expect(readyToSubmit?.remaining_required_fields).toEqual([]);
    expect(readyToSubmit?.can_submit).toBe(true);
    expect(readyToSubmit?.stage).toBe('ready_to_submit');
  });

  it('builds create/edit/view sessions through adapters', () => {
    const manager = new FormSessionManager();

    const createInput = createAntdFormSessionInput({
      surface_id: 'drawer:create',
      current_url: '/admin/ai/agents/new',
      fields: [
        {
          name: 'name',
          rules: [{ required: true }],
        },
      ],
      current_values: {},
      initial_values: {},
    });
    const createSession = manager.upsertSession(createInput);
    expect(createSession.mode).toBe('create');
    expect(createSession.entity_name).toBe('agent');

    const editInput = createVbenFormSessionInput({
      surface_id: 'drawer:edit',
      current_url: '/admin/ai/agents/42/edit',
      schema: [
        {
          fieldName: 'name',
          label: 'Name',
          required: true,
        },
      ],
      current_values: { id: 42, name: 'Existing Agent' },
      initial_values: { id: 42, name: 'Existing Agent' },
    });
    const editSession = manager.upsertSession(editInput);
    expect(editSession.mode).toBe('edit');
    expect(editSession.record_id).toBe(42);

    const viewInput = createVbenFormSessionInput({
      surface_id: 'drawer:view',
      current_url: '/admin/ai/agents/view/7',
      readonly: true,
      schema: [
        {
          fieldName: 'name',
          componentProps: { readonly: true },
        },
      ],
      current_values: { id: 7, name: 'Readonly Agent' },
      initial_values: { id: 7, name: 'Readonly Agent' },
    });
    const viewSession = manager.upsertSession(viewInput);
    expect(viewSession.mode).toBe('view');
    expect(viewSession.can_submit).toBe(false);
  });

  it('exposes active session and field descriptor lookup', () => {
    const manager = new FormSessionManager();

    const first = manager.upsertSession({
      form_session_id: 'session-A',
      surface_id: 'surface-A',
      fields: [{ name: 'name', value: 'A' }],
    });
    const second = manager.upsertSession({
      form_session_id: 'session-B',
      surface_id: 'surface-B',
      fields: [{ name: 'title', value: 'B' }],
    });

    expect(manager.getActiveSession()?.form_session_id).toBe(second.form_session_id);
    expect(manager.getActiveSession('surface-A')?.form_session_id).toBe(
      first.form_session_id,
    );
    expect(manager.getActiveFieldDescriptors('surface-A').map((f) => f.name)).toEqual(
      ['name'],
    );
    expect(manager.getFieldDescriptor('session-B', 'title')?.value).toBe('B');
  });
});
