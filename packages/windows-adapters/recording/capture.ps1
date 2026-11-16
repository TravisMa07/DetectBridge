# Real disposable-runner capture. Never run against an operator's Windows host.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'disposable_windows_runner_required' }
$directory = Join-Path $env:RUNNER_TEMP 'detectbridge-p11-originals'
$sealed = Join-Path $env:RUNNER_TEMP 'detectbridge-p11-sealed'
if (Test-Path $directory) { throw 'capture_directory_exists' }
New-Item -ItemType Directory $directory, $sealed | Out-Null
$utf8 = [Text.UTF8Encoding]::new($false)
function Save-Json($name, $value) {
    [IO.File]::WriteAllText((Join-Path $directory $name), (ConvertTo-Json -Depth 30 -InputObject $value), $utf8)
}
function Native($exe, $arguments, $name) {
    & $exe @arguments *> (Join-Path $directory $name)
    if ($LASTEXITCODE -ne 0) { throw 'native_capture_operation_failed' }
}
$installed = $false
$policySaved = $false
$key = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Policies\System\Audit'
$old = Get-ItemProperty -Path $key -Name ProcessCreationIncludeCmdLine_Enabled -ErrorAction SilentlyContinue
$oldValue = if ($null -ne $old) { $old.ProcessCreationIncludeCmdLine_Enabled } else { $null }
try {
    if (Get-Service Sysmon* -ErrorAction SilentlyContinue) { throw 'preexisting_sysmon_not_modified' }
    # The public recipient has no private key and is supplied by the local owner.
    $certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new([Convert]::FromBase64String($env:P11_RECIPIENT_CERT))
    if ($certificate.HasPrivateKey -or [Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPublicKey($certificate).KeySize -lt 3072) { throw 'invalid_public_recipient' }
    $expectationPath = Join-Path $PSScriptRoot 'expectations.json'
    $expected = Get-Content -Raw $expectationPath | ConvertFrom-Json
    Copy-Item $expectationPath (Join-Path $directory 'action-expectations.json')
    Copy-Item $PSCommandPath (Join-Path $directory 'capture.ps1')
    Save-Json 'host.json' ([ordered]@{
        machine_guid = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Cryptography').MachineGuid
        product_uuid = (Get-CimInstance Win32_ComputerSystemProduct).UUID
        computer = (Get-CimInstance Win32_ComputerSystem | Select-Object Name, DNSHostName, Domain)
        dns = [ordered]@{ hostname = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().HostName; domain = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().DomainName }
        boot_utc = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
        os = (Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber)
        identity = [ordered]@{ name = [Security.Principal.WindowsIdentity]::GetCurrent().Name; sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value }
        origin = [ordered]@{ repository = $env:GITHUB_REPOSITORY; commit = $env:GITHUB_SHA; run_id = $env:GITHUB_RUN_ID; run_attempt = $env:GITHUB_RUN_ATTEMPT; job = $env:GITHUB_JOB; runner_os = $env:RUNNER_OS; runner_arch = $env:RUNNER_ARCH; image_os = $env:ImageOS; image_version = $env:ImageVersion }
        queried_utc = [DateTime]::UtcNow.ToString('o')
    })
    $zip = Join-Path $env:RUNNER_TEMP 'detectbridge-sysmon.zip'
    Invoke-WebRequest 'https://download.sysinternals.com/files/Sysmon.zip' -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne '00ecf1b46aec99299d3ae0bca79dc621458bd014b20b509d7c5c8e8c8611aa54') { throw 'sysmon_package_drift' }
    $sysmonDir = Join-Path $env:RUNNER_TEMP 'detectbridge-sysmon'
    Expand-Archive $zip $sysmonDir
    $sysmon = Join-Path $sysmonDir 'Sysmon64.exe'
    $signature = Get-AuthenticodeSignature $sysmon
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') { throw 'sysmon_signature_invalid' }
    Copy-Item (Join-Path $sysmonDir 'Eula.txt') (Join-Path $directory 'sysmon-license.txt')
    Save-Json 'sysmon.json' ([ordered]@{ url = 'https://download.sysinternals.com/files/Sysmon.zip'; zip_sha256 = (Get-FileHash $zip).Hash.ToLowerInvariant(); binary_sha256 = (Get-FileHash $sysmon).Hash.ToLowerInvariant(); file_version = (Get-Item $sysmon).VersionInfo.FileVersion; signature_status = [string]$signature.Status; signer = $signature.SignerCertificate.Subject; signer_thumbprint = $signature.SignerCertificate.Thumbprint })
    Native auditpol.exe @('/backup', "/file:$directory\audit-policy-before.csv") 'audit-backup.txt'
    $policySaved = $true
    Native auditpol.exe @('/set', '/subcategory:{0CCE922B-69AE-11D9-BED3-505054503030}', '/success:enable') 'audit-set.txt'
    New-Item $key -Force | Out-Null
    New-ItemProperty $key -Name ProcessCreationIncludeCmdLine_Enabled -Value 1 -PropertyType DWord -Force | Out-Null
    Native auditpol.exe @('/get', '/subcategory:{0CCE922B-69AE-11D9-BED3-505054503030}', '/r') 'audit-policy-active.csv'
    Save-Json 'command-line-policy.json' (Get-ItemPropertyValue $key -Name ProcessCreationIncludeCmdLine_Enabled)
    $start = [DateTime]::UtcNow
    Native $sysmon @('-accepteula', '-i') 'sysmon-install.txt'
    $installed = $true
    $actions = @()
    foreach ($action in $expected.actions) {
        if (-not (Test-Path $action.image)) { throw 'expected_windows_image_missing' }
        $info = [Diagnostics.ProcessStartInfo]::new($action.image, $action.arguments)
        $info.UseShellExecute = $false
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $before = [DateTime]::UtcNow.ToString('o')
        $process = [Diagnostics.Process]::Start($info)
        $nativeId = $process.Id
        $stdout = $process.StandardOutput.ReadToEnd()
        $stderr = $process.StandardError.ReadToEnd()
        if (-not $process.WaitForExit(10000) -or $process.ExitCode -ne $action.exit_code) { throw 'controlled_action_failed' }
        $actions += [ordered]@{ id = $action.id; image = $action.image; arguments = $action.arguments; pid = $nativeId; parent_pid = $PID; exit_code = $process.ExitCode; started_utc = $before; ended_utc = [DateTime]::UtcNow.ToString('o'); binary_sha256 = (Get-FileHash $action.image).Hash.ToLowerInvariant() }
    }
    Save-Json 'actions.json' $actions
    $selection = @()
    foreach ($family in $expected.families) {
        $channel = if ($family -eq 'security') { 'Security' } else { 'Microsoft-Windows-Sysmon/Operational' }
        $eventId = if ($family -eq 'security') { 4688 } else { 1 }
        $events = @()
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            $events = @(Get-WinEvent -FilterHashtable @{ LogName = $channel; Id = $eventId; StartTime = $start } -ErrorAction SilentlyContinue)
            $found = @()
            foreach ($action in $actions) {
                $candidates = @($events | Where-Object {
                    $xml = [xml]$_.ToXml()
                    $data = @{}; foreach ($item in $xml.Event.EventData.Data) { $data[[string]$item.Name] = [string]$item.'#text' }
                    $nativePid = if ($family -eq 'security') { [Convert]::ToInt32($data['NewProcessId'], 16) } else { [int]$data['ProcessId'] }
                    $image = if ($family -eq 'security') { $data['NewProcessName'] } else { $data['Image'] }
                    $nativePid -eq $action.pid -and $image -ieq $action.image
                })
                if ($candidates.Count -eq 1) { $found += @{ action = $action.id; event = $candidates[0] } }
            }
            if ($found.Count -eq 2) { break }
            Start-Sleep -Milliseconds 500
        }
        if ($found.Count -ne 2) { throw 'native_process_records_incomplete' }
        foreach ($item in $found) {
            $name = "$family-$($item.action).xml"
            $text = $item.event.ToXml()
            [IO.File]::WriteAllText((Join-Path $directory $name), $text, $utf8)
            $selection += @{ filename = $name; family = $family; action = $item.action; event_record_id = $item.event.RecordId; observed_utc = [DateTime]::UtcNow.ToString('o') }
        }
    }
    $control = @(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Sysmon/Operational';Id=4;StartTime=$start} -ErrorAction SilentlyContinue)
    if ($control.Count -lt 1) { throw 'native_service_record_missing' }
    [IO.File]::WriteAllText((Join-Path $directory 'sysmon-control.xml'), $control[-1].ToXml(), $utf8)
    $selection += @{ filename='sysmon-control.xml';family='sysmon';action='service-state';event_record_id=$control[-1].RecordId;observed_utc=[DateTime]::UtcNow.ToString('o') }
    Save-Json 'selection.json' $selection
    Save-Json 'capture-complete.json' @{ completed_utc = [DateTime]::UtcNow.ToString('o'); selected_records = $selection.Count }
} catch {
    # Details and any source values remain local to this disposable runner.
    [IO.File]::WriteAllText((Join-Path $directory 'capture-error.txt'), $_.ToString(), $utf8)
    throw 'windows_recording_failed_no_plaintext_upload'
} finally {
    if ($installed) { & $sysmon -u force *> (Join-Path $directory 'sysmon-uninstall.txt') }
    if ($policySaved) { & auditpol.exe /restore "/file:$directory\audit-policy-before.csv" *> (Join-Path $directory 'audit-restore.txt') }
    if ($null -eq $oldValue) { Remove-ItemProperty $key -Name ProcessCreationIncludeCmdLine_Enabled -ErrorAction SilentlyContinue } else { Set-ItemProperty $key -Name ProcessCreationIncludeCmdLine_Enabled -Value $oldValue }
}
# Encrypt only after successful capture. No private keys or executable packages in the archive.
Add-Type -AssemblyName System.Security.Cryptography.Pkcs
$archive = Join-Path $env:RUNNER_TEMP 'detectbridge-p11-originals.zip'
Compress-Archive -Path "$directory\*" -DestinationPath $archive
$content = [Security.Cryptography.Pkcs.ContentInfo]::new([IO.File]::ReadAllBytes($archive))
$envelope = [Security.Cryptography.Pkcs.EnvelopedCms]::new($content, [Security.Cryptography.Pkcs.AlgorithmIdentifier]::new([Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.1.42')))
$envelope.Encrypt([Security.Cryptography.Pkcs.CmsRecipient]::new($certificate))
[IO.File]::WriteAllBytes((Join-Path $sealed 'recording.p7m'), $envelope.Encode())
Write-Output 'Controlled recording encrypted; no source values logged.'
