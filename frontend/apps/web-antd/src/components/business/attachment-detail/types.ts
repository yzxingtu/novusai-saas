export interface AttachmentDetailField {
  color?: string;
  kind?: 'code' | 'tag' | 'text';
  label: string;
  show?: boolean;
  value: null | number | string | undefined;
}

export interface AttachmentDetailSection {
  fields: AttachmentDetailField[];
  title?: string;
}
