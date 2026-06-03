[CmdletBinding()]
param(
    [string]$Path = "."
)

$ErrorActionPreference = "Stop"

function ConvertTo-YudiBaseMap {
    param(
        [string]$Content
    )

    $metadata = @{}

    if ([string]::IsNullOrWhiteSpace($Content)) {
        return $metadata
    }

    try {
        $json = $Content | ConvertFrom-Json -ErrorAction Stop
        foreach ($property in $json.PSObject.Properties) {
            $metadata[$property.Name] = $property.Value
        }
        return $metadata
    }
    catch {
        foreach ($line in ($Content -split "`r?`n")) {
            $trimmed = $line.Trim()
            if ($trimmed -eq "" -or $trimmed.StartsWith("#")) {
                continue
            }

            if ($trimmed -match "^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*[:=]\s*(.*?)\s*$") {
                $key = $Matches[1]
                $value = $Matches[2].Trim().Trim('"').Trim("'")
                $metadata[$key] = $value
            }
        }
    }

    return $metadata
}

function Test-HasValue {
    param(
        [hashtable]$Metadata,
        [string]$Key
    )

    if (-not $Metadata.ContainsKey($Key)) {
        return $false
    }

    return -not [string]::IsNullOrWhiteSpace([string]$Metadata[$Key])
}

try {
    $target = (Resolve-Path -LiteralPath $Path).ProviderPath
}
catch {
    Write-Output "Path does not exist: $Path"
    exit 1
}

$baseFile = Join-Path -Path $target -ChildPath ".yudi-base"
if (-not (Test-Path -LiteralPath $baseFile -PathType Leaf)) {
    Write-Output "Missing required .yudi-base file: $baseFile"
    exit 1
}

$metadata = ConvertTo-YudiBaseMap -Content (Get-Content -LiteralPath $baseFile -Raw)
$missing = New-Object System.Collections.Generic.List[string]

if (-not (Test-HasValue -Metadata $metadata -Key "upstream")) {
    $missing.Add("upstream")
}

if (-not ((Test-HasValue -Metadata $metadata -Key "base_tag") -or (Test-HasValue -Metadata $metadata -Key "base_commit"))) {
    $missing.Add("base_tag or base_commit")
}

if (-not (Test-HasValue -Metadata $metadata -Key "last_synced_at")) {
    $missing.Add("last_synced_at")
}

if ($missing.Count -gt 0) {
    Write-Output "Missing required .yudi-base fields: $($missing -join ', ')"
    exit 1
}

Write-Output "Yudi base metadata is valid: $baseFile"
exit 0
