export interface ConfigField {
  key: string;
  format?: string;
  type: string;
  title: string;
  description: string;
  default: unknown;
  enum?: string[];
  minimum?: number;
  maximum?: number;
}

export interface TenantOption {
  id: number;
  name: string;
}
