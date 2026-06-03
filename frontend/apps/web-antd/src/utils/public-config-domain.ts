export function shouldRequestTenantPublicConfig(
  isDomainDetected: boolean,
  isDomainTenantDomain: boolean | null,
): boolean {
  return isDomainDetected && isDomainTenantDomain === true;
}
