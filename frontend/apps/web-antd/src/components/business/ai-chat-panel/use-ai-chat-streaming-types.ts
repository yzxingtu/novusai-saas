export interface PendingInteractionUpdate {
  action?: string;
  auto_approved?: boolean;
  kind: 'action_buttons' | 'pending_confirmation' | 'pending_consent';
  rejected?: boolean;
  table?: string;
  tool_name?: string;
  value?: string;
}
