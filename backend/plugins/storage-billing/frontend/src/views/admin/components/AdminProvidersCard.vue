<script lang="ts" setup>
import type { BindingScopeType, PeriodType, ProviderCode } from '../../../types';

type CapabilitySummary = {
  official_billing_lag_days?: null | number;
  official_target_rule?: string;
  recommended_scope_types: BindingScopeType[];
  settlement_cycle?: string;
  settlement_mode?: string;
  supported_period_types: PeriodType[];
};

type ProfileRecord = Record<string, unknown> & {
  bill_source?: string;
  capability_message?: string;
  enabled?: boolean;
};

type ValidationRecord = Record<string, unknown> & {
  errors: string[];
  required_fields?: string[];
  status: string;
  warnings: string[];
};

type ProviderFieldMap = Record<ProviderCode, readonly string[]>;

const props = defineProps<{
  billSourceOptions: (code: ProviderCode) => Array<{ label: string; value: string }>;
  canConfigureAdmin: boolean;
  capabilityCycleLabel: (value: string | undefined) => string;
  capabilityModeLabel: (value: string | undefined) => string;
  capabilityPeriodLabel: (value: PeriodType) => string;
  capabilityTargetRuleLabel: (value: string | undefined) => string;
  fieldLabel: (field: string) => string;
  hasVisibleProviders: boolean;
  prettyStatus: (status: string) => string;
  profileFields: ProviderFieldMap;
  profileWarnings: (code: ProviderCode) => string;
  profiles: Record<ProviderCode, ProfileRecord>;
  providerCapabilitySummary: (code: ProviderCode) => CapabilitySummary;
  providerCapabilityTags: (code: ProviderCode) => string[];
  providerLabel: (code: ProviderCode) => string;
  providerLabelFromAny: (code: string) => string;
  providerRuntimeValue: (value: null | string | undefined) => string;
  providerStorageContext: (code: ProviderCode) => {
    base_url?: null | string;
    bucket_name?: null | string;
    current_driver?: string;
    endpoint?: null | string;
    prefix?: null | string;
    region?: null | string;
    root_path?: null | string;
  };
  providerStorageMatch: (code: ProviderCode) => boolean;
  providerStorageReady: (code: ProviderCode) => boolean;
  statusColor: (status: string) => string;
  validateProvider: (code: ProviderCode) => void;
  validations: Record<ProviderCode, ValidationRecord>;
  visibleProviderCodes: ProviderCode[];
}>();
</script>

<template>
  <Card :title="$t('plugin.storage-billing.admin.providers.title')" class="block">
    <div class="section-subtitle">{{ $t('plugin.storage-billing.admin.providers.subtitle') }}</div>
    <Alert
      v-if="!props.hasVisibleProviders"
      class="block"
      :message="$t('plugin.storage-billing.admin.providers.noActiveDriver')"
      type="warning"
      show-icon
    />
    <div v-else class="providers">
      <Card v-for="code in props.visibleProviderCodes" :key="code">
        <template #title>
          <Space wrap>
            <span>{{ props.providerLabel(code) }}</span>
            <Tag :color="props.statusColor(props.validations[code].status)">
              {{ props.prettyStatus(props.validations[code].status) }}
            </Tag>
            <Tag v-for="tag in props.providerCapabilityTags(code)" :key="`${code}-${tag}`" color="blue">{{ tag }}</Tag>
          </Space>
        </template>
        <Alert
          v-if="props.profiles[code].capability_message"
          class="block"
          :message="props.providerLabel(code)"
          :description="String(props.profiles[code].capability_message)"
          type="info"
          show-icon
        />
        <Alert
          v-if="props.profileWarnings(code)"
          class="block"
          :message="props.providerLabel(code)"
          :description="props.profileWarnings(code)"
          :type="props.validations[code].errors.length ? 'error' : 'warning'"
          show-icon
        />
        <div class="capability-grid">
          <div class="capability-item">
            <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.mode') }}</span>
            <strong>{{ props.capabilityModeLabel(props.providerCapabilitySummary(code).settlement_mode) || '-' }}</strong>
          </div>
          <div class="capability-item">
            <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.cycle') }}</span>
            <strong>{{ props.capabilityCycleLabel(props.providerCapabilitySummary(code).settlement_cycle) || '-' }}</strong>
          </div>
          <div class="capability-item">
            <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.targetRule') }}</span>
            <strong>{{ props.capabilityTargetRuleLabel(props.providerCapabilitySummary(code).official_target_rule) }}</strong>
          </div>
          <div class="capability-item">
            <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.lagDays') }}</span>
            <strong>{{ props.providerCapabilitySummary(code).official_billing_lag_days ?? '-' }}</strong>
          </div>
          <div class="capability-item capability-item-wide">
            <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.periodTypes') }}</span>
            <strong>
              {{
                props.providerCapabilitySummary(code).supported_period_types
                  .map((item) => props.capabilityPeriodLabel(item) || item)
                  .join(' / ') || '-'
              }}
            </strong>
          </div>
          <div class="capability-item capability-item-wide">
            <span class="capability-label">{{ $t('plugin.storage-billing.admin.providers.capabilities.recommendedScopes') }}</span>
            <strong>
              {{
                props.providerCapabilitySummary(code).recommended_scope_types
                  .map((item) => $t(`plugin.storage-billing.admin.bindings.scope.${item}`))
                  .join(' / ') || '-'
              }}
            </strong>
          </div>
        </div>
        <Descriptions :column="2" class="provider-runtime" size="small">
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.configSource')">
            {{ $t('plugin.storage-billing.admin.providers.runtime.source.platform_storage') }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.currentDriver')">
            {{ props.providerLabelFromAny(props.providerStorageContext(code).current_driver || '-') }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.driverMatch')">
            <Tag :color="props.providerStorageMatch(code) ? 'success' : 'error'">
              {{
                $t(
                  props.providerStorageMatch(code)
                    ? 'plugin.storage-billing.admin.providers.runtime.match'
                    : 'plugin.storage-billing.admin.providers.runtime.mismatch',
                )
              }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.credentialStatus')">
            <Tag :color="props.providerStorageReady(code) ? 'success' : 'warning'">
              {{
                $t(
                  props.providerStorageReady(code)
                    ? 'plugin.storage-billing.admin.providers.runtime.configured'
                    : 'plugin.storage-billing.admin.providers.runtime.missing',
                )
              }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.bucket')">
            {{ props.providerRuntimeValue(props.providerStorageContext(code).bucket_name) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.baseUrl')">
            {{ props.providerRuntimeValue(props.providerStorageContext(code).base_url) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.region')">
            {{ props.providerRuntimeValue(props.providerStorageContext(code).region) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.endpoint')">
            {{ props.providerRuntimeValue(props.providerStorageContext(code).endpoint) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.prefix')">
            {{ props.providerRuntimeValue(props.providerStorageContext(code).prefix) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('plugin.storage-billing.admin.providers.runtime.rootPath')">
            {{ props.providerRuntimeValue(props.providerStorageContext(code).root_path) }}
          </Descriptions.Item>
        </Descriptions>
        <Form layout="vertical">
          <FormItem :label="$t('plugin.storage-billing.admin.field.enabled')">
            <Switch v-model:checked="props.profiles[code].enabled" />
          </FormItem>
          <FormItem v-for="field in props.profileFields[code]" :key="field" :label="props.fieldLabel(field)">
            <template #extra>
              <Space wrap>
                <Tag :color="(props.validations[code].required_fields ?? []).includes(field) ? 'error' : 'default'">
                  {{
                    (props.validations[code].required_fields ?? []).includes(field)
                      ? $t('plugin.storage-billing.admin.providers.required')
                      : $t('plugin.storage-billing.admin.providers.optional')
                  }}
                </Tag>
              </Space>
            </template>
            <Select
              v-if="field === 'bill_source'"
              v-model:value="props.profiles[code][field]"
              :options="props.billSourceOptions(code)"
            />
            <Input
              v-else
              v-model:value="props.profiles[code][field]"
              type="text"
            />
          </FormItem>
        </Form>
        <div v-if="props.canConfigureAdmin" class="actions">
          <Button @click="props.validateProvider(code)">{{ $t('plugin.storage-billing.admin.providers.validate') }}</Button>
        </div>
      </Card>
    </div>
  </Card>
</template>
