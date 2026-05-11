[CmdletBinding()]
param(
    [string]$Path = "."
)

$ErrorActionPreference = "Stop"

try {
    $root = (Resolve-Path -LiteralPath $Path).ProviderPath
}
catch {
    Write-Output "Path does not exist: $Path"
    exit 1
}

$requiredPaths = @(
    "business/README.md",
    "business/_template/README.md",
    "business/_template/backend/README.md",
    "business/_template/frontend/README.md",
    "business/_template/shared/README.md",
    "business/_template/adapters/yudi-plugin/README.md",
    "customer/README.md",
    "customer/_template/README.md",
    "customer/_template/overlays/README.md",
    "customer/_template/seeds/README.md",
    "customer/_template/decisions/README.md",
    "extensions/README.md",
    "extensions/_template/README.md"
)

$missing = New-Object System.Collections.Generic.List[string]
foreach ($relativePath in $requiredPaths) {
    $candidate = Join-Path -Path $root -ChildPath $relativePath
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        $missing.Add($relativePath)
    }
}

if ($missing.Count -gt 0) {
    Write-Output "Missing customer boundary files: $($missing -join ', ')"
    exit 1
}

$scanRoots = @(
    "README.md",
    "README.zh-CN.md",
    "CUSTOMER_PROJECT.md",
    "docs",
    ".trellis",
    ".github",
    "business",
    "customer",
    "extensions"
)

$stalePatterns = @(
    "customer/ecommerce-erp/plugins",
    "customer\\ecommerce-erp\\plugins",
    "customer business pages",
    "Customer-specific work belongs under customer",
    "业务代码.*customer/.*/plugins",
    "客户.*业务.*plugins"
)

$violations = New-Object System.Collections.Generic.List[string]
foreach ($scanRoot in $scanRoots) {
    $absolute = Join-Path -Path $root -ChildPath $scanRoot
    if (-not (Test-Path -LiteralPath $absolute)) {
        continue
    }

    $files = @()
    if (Test-Path -LiteralPath $absolute -PathType Leaf) {
        $files = @((Get-Item -LiteralPath $absolute))
    }
    else {
        $files = Get-ChildItem -LiteralPath $absolute -Recurse -File -Include *.md,*.json,*.yaml,*.yml
    }

    foreach ($file in $files) {
        $content = Get-Content -LiteralPath $file.FullName -Raw
        foreach ($pattern in $stalePatterns) {
            if ($content -match $pattern) {
                $relative = [System.IO.Path]::GetRelativePath($root, $file.FullName)
                $violations.Add("$relative matches stale pattern: $pattern")
            }
        }
    }
}

if ($violations.Count -gt 0) {
    Write-Output "Customer boundary violations found:"
    foreach ($violation in $violations) {
        Write-Output " - $violation"
    }
    exit 1
}

Write-Output "Customer boundary files and guidance are valid: $root"
exit 0
