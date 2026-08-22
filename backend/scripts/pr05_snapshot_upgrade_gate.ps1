[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDatabase,

    [Parameter(Mandatory = $true)]
    [ValidatePattern("^rotas_pr05_[a-zA-Z0-9_]+$")]
    [string]$TargetDatabase,

    [Parameter(Mandatory = $true)]
    [string]$DumpPath,

    [Parameter(Mandatory = $true)]
    [string]$ReportPath,

    [string]$DatabaseHost = "localhost",
    [int]$DatabasePort = 5432,
    [string]$DatabaseUser = "rotas",
    [string]$ExpectedSourceRevision = "95929ae669b9",
    [string]$ExpectedHead = "rec13",
    [string]$LockTimeout = "5s",
    [string]$StatementTimeout = "15min",
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\16\bin",
    [string]$BackendPath = (Split-Path -Parent $PSScriptRoot),
    [switch]$ConfirmAnonymized,
    [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $ConfirmAnonymized) {
    throw "Refusing snapshot: pass -ConfirmAnonymized after verifying the source contains no live PII."
}
if ($SourceDatabase -eq $TargetDatabase) {
    throw "SourceDatabase and TargetDatabase must be different."
}
if (-not $env:PGPASSWORD) {
    throw "PGPASSWORD must be supplied through the process environment."
}
if (-not $env:PR05_ALEMBIC_URL_TEMPLATE) {
    throw "PR05_ALEMBIC_URL_TEMPLATE must be set and contain the literal token {database}."
}
if (-not $env:PR05_ALEMBIC_URL_TEMPLATE.Contains("{database}")) {
    throw "PR05_ALEMBIC_URL_TEMPLATE must contain the literal token {database}."
}

$psql = Join-Path $PostgresBin "psql.exe"
$pgDump = Join-Path $PostgresBin "pg_dump.exe"
$pgRestore = Join-Path $PostgresBin "pg_restore.exe"
$createdb = Join-Path $PostgresBin "createdb.exe"
$dropdb = Join-Path $PostgresBin "dropdb.exe"
$python = Join-Path $BackendPath ".venv\Scripts\python.exe"

foreach ($tool in @($psql, $pgDump, $pgRestore, $createdb, $dropdb, $python)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
        throw "Required executable not found: $tool"
    }
}

$dumpDirectory = Split-Path -Parent $DumpPath
$reportDirectory = Split-Path -Parent $ReportPath
foreach ($directory in @($dumpDirectory, $reportDirectory)) {
    if ($directory -and -not (Test-Path -LiteralPath $directory -PathType Container)) {
        New-Item -ItemType Directory -Path $directory | Out-Null
    }
}
if (Test-Path -LiteralPath $DumpPath) {
    throw "DumpPath already exists; refusing to overwrite: $DumpPath"
}
if (Test-Path -LiteralPath $ReportPath) {
    throw "ReportPath already exists; refusing to overwrite: $ReportPath"
}

function Invoke-PostgresScalar {
    param(
        [Parameter(Mandatory = $true)][string]$Database,
        [Parameter(Mandatory = $true)][string]$Sql
    )
    $value = & $psql `
        -h $DatabaseHost `
        -p $DatabasePort `
        -U $DatabaseUser `
        -d $Database `
        -X -A -t `
        -v ON_ERROR_STOP=1 `
        -c $Sql
    if ($LASTEXITCODE -ne 0) {
        throw "psql failed for database $Database."
    }
    return ($value | Out-String).Trim()
}

$targetCreated = $false
$succeeded = $false
$upgradeStdout = "$DumpPath.upgrade.stdout.log"
$upgradeStderr = "$DumpPath.upgrade.stderr.log"
$startedAt = [DateTimeOffset]::UtcNow
$previousPgOptions = $env:PGOPTIONS

try {
    $targetExists = Invoke-PostgresScalar `
        -Database "postgres" `
        -Sql "SELECT count(*) FROM pg_database WHERE datname = '$TargetDatabase';"
    if ($targetExists -ne "0") {
        throw "Target database already exists; refusing to overwrite: $TargetDatabase"
    }

    $sourceRevision = Invoke-PostgresScalar `
        -Database $SourceDatabase `
        -Sql "SELECT version_num FROM alembic_version;"
    if ($sourceRevision -ne $ExpectedSourceRevision) {
        throw "Source revision is $sourceRevision; expected $ExpectedSourceRevision."
    }

    $dumpDuration = Measure-Command {
        & $pgDump `
            -h $DatabaseHost `
            -p $DatabasePort `
            -U $DatabaseUser `
            -d $SourceDatabase `
            -Fc `
            --no-owner `
            --no-privileges `
            -f $DumpPath
    }
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed."
    }

    & $createdb `
        -h $DatabaseHost `
        -p $DatabasePort `
        -U $DatabaseUser `
        -T template0 `
        $TargetDatabase
    if ($LASTEXITCODE -ne 0) {
        throw "createdb failed."
    }
    $targetCreated = $true

    $restoreDuration = Measure-Command {
        & $pgRestore `
            -h $DatabaseHost `
            -p $DatabasePort `
            -U $DatabaseUser `
            -d $TargetDatabase `
            --no-owner `
            --no-privileges `
            --exit-on-error `
            $DumpPath
    }
    if ($LASTEXITCODE -ne 0) {
        throw "pg_restore failed."
    }

    $restoredRevision = Invoke-PostgresScalar `
        -Database $TargetDatabase `
        -Sql "SELECT version_num FROM alembic_version;"
    if ($restoredRevision -ne $ExpectedSourceRevision) {
        throw "Restored revision is $restoredRevision; expected $ExpectedSourceRevision."
    }

    $env:DATABASE_URL = $env:PR05_ALEMBIC_URL_TEMPLATE.Replace(
        "{database}",
        $TargetDatabase
    )

    $observedLocks = [System.Collections.Generic.HashSet[string]]::new()
    $maxWaitingLocks = 0
    $lockSamples = 0
    $lockMonitorErrors = 0
    $env:PGOPTIONS = (
        "$previousPgOptions -c lock_timeout=$LockTimeout " +
        "-c statement_timeout=$StatementTimeout"
    ).Trim()
    $upgradeTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process `
        -FilePath $python `
        -ArgumentList "-m", "alembic", "upgrade", "head" `
        -WorkingDirectory $BackendPath `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $upgradeStdout `
        -RedirectStandardError $upgradeStderr

    while (-not $process.HasExited) {
        $lockRows = & $psql `
            -h $DatabaseHost `
            -p $DatabasePort `
            -U $DatabaseUser `
            -d $TargetDatabase `
            -X -A -t -F "|" `
            -c (
                "SELECT l.mode,l.granted,coalesce(c.relname,'') " +
                "FROM pg_locks l " +
                "JOIN pg_stat_activity a ON a.pid=l.pid " +
                "LEFT JOIN pg_class c ON c.oid=l.relation " +
                "WHERE a.datname=current_database() " +
                "AND a.application_name <> 'psql';"
            )
        if ($LASTEXITCODE -ne 0) {
            $lockMonitorErrors++
            Start-Sleep -Milliseconds 100
            $process.Refresh()
            continue
        }
        foreach ($row in $lockRows) {
            if ($row) {
                [void]$observedLocks.Add($row)
            }
        }
        $waitingLocks = @($lockRows | Where-Object { $_ -match "\|f\|" }).Count
        if ($waitingLocks -gt $maxWaitingLocks) {
            $maxWaitingLocks = $waitingLocks
        }
        $lockSamples++
        Start-Sleep -Milliseconds 100
        $process.Refresh()
    }
    $upgradeTimer.Stop()
    if ($process.ExitCode -ne 0) {
        throw "Alembic upgrade failed. See $upgradeStderr"
    }
    if ($lockMonitorErrors -gt 0) {
        throw "Lock monitor failed in $lockMonitorErrors samples."
    }

    Push-Location $BackendPath
    try {
        $finalRevisionOutput = & $python -m alembic current
        if ($LASTEXITCODE -ne 0) {
            throw "alembic current failed."
        }
        $checkOutput = & $python -m alembic check
        if ($LASTEXITCODE -ne 0) {
            throw "alembic check detected schema drift."
        }
    }
    finally {
        Pop-Location
    }

    $finalRevision = ($finalRevisionOutput | Out-String).Trim()
    if ($finalRevision -notmatch [regex]::Escape($ExpectedHead)) {
        throw "Final revision is $finalRevision; expected head $ExpectedHead."
    }

    $dumpFile = Get-Item -LiteralPath $DumpPath
    $dumpHash = Get-FileHash -LiteralPath $DumpPath -Algorithm SHA256
    $lockModes = @(
        $observedLocks |
            ForEach-Object { ($_ -split "\|")[0] } |
            Sort-Object -Unique
    )
    $report = [ordered]@{
        gate = "PR-05"
        started_at_utc = $startedAt.ToString("o")
        completed_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
        source_database = $SourceDatabase
        source_revision = $sourceRevision
        target_database = $TargetDatabase
        expected_head = $ExpectedHead
        final_revision = $finalRevision
        dump_bytes = $dumpFile.Length
        dump_sha256 = $dumpHash.Hash.ToLowerInvariant()
        dump_seconds = [math]::Round($dumpDuration.TotalSeconds, 3)
        restore_seconds = [math]::Round($restoreDuration.TotalSeconds, 3)
        upgrade_seconds = [math]::Round($upgradeTimer.Elapsed.TotalSeconds, 3)
        lock_samples = $lockSamples
        max_waiting_locks = $maxWaitingLocks
        lock_monitor_errors = $lockMonitorErrors
        observed_lock_modes = $lockModes
        lock_timeout = $LockTimeout
        statement_timeout = $StatementTimeout
        alembic_check = ($checkOutput | Out-String).Trim()
        artifacts_retained = [bool]$KeepArtifacts
    }
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding utf8
    $succeeded = $true
    Get-Content -LiteralPath $ReportPath
}
finally {
    $env:PGOPTIONS = $previousPgOptions
    if ($succeeded -and -not $KeepArtifacts) {
        $cleanupFailed = $false
        if ($targetCreated) {
            & $dropdb `
                -h $DatabaseHost `
                -p $DatabasePort `
                -U $DatabaseUser `
                $TargetDatabase
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Could not remove target database $TargetDatabase."
                $cleanupFailed = $true
            }
        }
        foreach ($artifact in @($DumpPath, $upgradeStdout, $upgradeStderr)) {
            if (Test-Path -LiteralPath $artifact) {
                Remove-Item -LiteralPath $artifact -Force
            }
        }
        if ($cleanupFailed) {
            throw "Gate completed, but cleanup failed."
        }
    }
    elseif (-not $succeeded) {
        Write-Warning "Gate failed; target database and diagnostic artifacts were preserved."
    }
}
