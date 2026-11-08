<#
=============================================================================
  GodMode TeleKey - Universal Windows Hardware USB Telegram Bridge
  Target Hardware Serial: 0377291581335169734
=============================================================================
#>

$BotToken = "8638559927:AAEsHxtIbdkRV24l7rK6qsZ_AkYmg1cCt1o"
$ChatID   = "8556430828"
$TargetSerial = "0377291581335169734"
$ApiUrl   = "https://api.telegram.org/bot$BotToken"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Send-TgMessage {
    param([string]$Text, [string]$ParseMode = "Markdown")
    $body = @{
        chat_id = $ChatID
        text = $Text
        parse_mode = $ParseMode
        reply_markup = @{
            keyboard = @(
                @(@{text="📊 Status"}, @{text="📸 Screenshot"}),
                @(@{text="🔒 Lock Screen"}, @{text="📋 Clipboard"}),
                @(@{text="⏏️ Eject USB"}, @{text="❓ Help"})
            )
            resize_keyboard = $true
            persistent = $true
        }
    } | ConvertTo-Json -Depth 5
    try {
        Invoke-RestMethod -Uri "$ApiUrl/sendMessage" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10 | Out-Null
    } catch {
        Write-Warning "Failed to send TG message: $_"
    }
}

function Send-TgPhoto {
    param([string]$FilePath, [string]$Caption = "")
    if (-not (Test-Path $FilePath)) { return }
    try {
        $boundary = [System.Guid]::NewGuid().ToString()
        $LF = "`r`n"
        $fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
        $fileName = [System.IO.Path]::GetFileName($FilePath)

        $bodyLines = @(
            "--$boundary",
            "Content-Disposition: form-data; name=`"chat_id`"",
            "",
            $ChatID,
            "--$boundary",
            "Content-Disposition: form-data; name=`"caption`"",
            "",
            $Caption,
            "--$boundary",
            "Content-Disposition: form-data; name=`"photo`"; filename=`"$fileName`"",
            "Content-Type: image/png",
            ""
        )
        $bodyPrefix = [System.Text.Encoding]::UTF8.GetBytes(($bodyLines -join $LF) + $LF)
        $bodySuffix = [System.Text.Encoding]::UTF8.GetBytes("$LF--$boundary--$LF")

        $allBytes = [byte[]]::new($bodyPrefix.Length + $fileBytes.Length + $bodySuffix.Length)
        [System.Buffer]::BlockCopy($bodyPrefix, 0, $allBytes, 0, $bodyPrefix.Length)
        [System.Buffer]::BlockCopy($fileBytes, 0, $allBytes, 0, $bodyPrefix.Length)
        [System.Buffer]::BlockCopy($fileBytes, 0, $allBytes, $bodyPrefix.Length, $fileBytes.Length)
        [System.Buffer]::BlockCopy($bodySuffix, 0, $allBytes, $bodyPrefix.Length + $fileBytes.Length, $bodySuffix.Length)

        $webReq = [System.Net.HttpWebRequest]::Create("$ApiUrl/sendPhoto")
        $webReq.Method = "POST"
        $webReq.ContentType = "multipart/form-data; boundary=$boundary"
        $webReq.ContentLength = $allBytes.Length
        $reqStream = $webReq.GetRequestStream()
        $reqStream.Write($allBytes, 0, $allBytes.Length)
        $reqStream.Close()
        $resp = $webReq.GetResponse()
        $resp.Close()
    } catch {
        Write-Warning "Failed to send photo: $_"
    }
}

function Send-TgDocument {
    param([string]$FilePath, [string]$Caption = "")
    if (-not (Test-Path $FilePath)) { return }
    try {
        $boundary = [System.Guid]::NewGuid().ToString()
        $LF = "`r`n"
        $fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
        $fileName = [System.IO.Path]::GetFileName($FilePath)

        $bodyLines = @(
            "--$boundary",
            "Content-Disposition: form-data; name=`"chat_id`"",
            "",
            $ChatID,
            "--$boundary",
            "Content-Disposition: form-data; name=`"caption`"",
            "",
            $Caption,
            "--$boundary",
            "Content-Disposition: form-data; name=`"document`"; filename=`"$fileName`"",
            "Content-Type: application/octet-stream",
            ""
        )
        $bodyPrefix = [System.Text.Encoding]::UTF8.GetBytes(($bodyLines -join $LF) + $LF)
        $bodySuffix = [System.Text.Encoding]::UTF8.GetBytes("$LF--$boundary--$LF")

        $allBytes = [byte[]]::new($bodyPrefix.Length + $fileBytes.Length + $bodySuffix.Length)
        [System.Buffer]::BlockCopy($bodyPrefix, 0, $allBytes, 0, $bodyPrefix.Length)
        [System.Buffer]::BlockCopy($fileBytes, 0, $allBytes, $bodyPrefix.Length, $fileBytes.Length)
        [System.Buffer]::BlockCopy($bodySuffix, 0, $allBytes, $bodyPrefix.Length + $fileBytes.Length, $bodySuffix.Length)

        $webReq = [System.Net.HttpWebRequest]::Create("$ApiUrl/sendDocument")
        $webReq.Method = "POST"
        $webReq.ContentType = "multipart/form-data; boundary=$boundary"
        $webReq.ContentLength = $allBytes.Length
        $reqStream = $webReq.GetRequestStream()
        $reqStream.Write($allBytes, 0, $allBytes.Length)
        $reqStream.Close()
        $resp = $webReq.GetResponse()
        $resp.Close()
    } catch {
        Write-Warning "Failed to send document: $_"
    }
}

function Take-Screenshot {
    $tmpPath = "$env:TEMP\tele_screen.png"
    if (Test-Path $tmpPath) { Remove-Item $tmpPath -Force }
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $gfx = [System.Drawing.Graphics]::FromImage($bmp)
    $gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bmp.Save($tmpPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $gfx.Dispose()
    $bmp.Dispose()
    return $tmpPath
}

function Is-UsbPresent {
    try {
        $drives = Get-CimInstance Win32_DiskDrive
        foreach ($d in $drives) {
            if ($d.PNPDeviceID -match $TargetSerial -or $d.SerialNumber -match $TargetSerial) {
                return $true
            }
        }
    } catch {}
    return $false
}

function Get-HostTelemetry {
    $hostname = $env:COMPUTERNAME
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback|vEthernet" } | Select-Object -First 1).IPAddress
    $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    $os = Get-CimInstance Win32_OperatingSystem
    $freeRamMB = [math]::Round($os.FreePhysicalMemory / 1024, 0)
    $totalRamMB = [math]::Round($os.TotalVisibleMemorySize / 1024, 0)
    $usedRamMB = $totalRamMB - $freeRamMB
    $ramPct = [math]::Round(($usedRamMB / $totalRamMB) * 100, 0)

    $battery = "AC"
    try {
        $bat = Get-CimInstance Win32_Battery
        if ($bat) {
            $battery = "$($bat.EstimatedChargeRemaining)% ($($bat.BatteryStatus))"
        }
    } catch {}

    return @{
        Host = $hostname
        IP = $ip
        CPU = "$cpu%"
        RAM = "$usedRamMB / $totalRamMB MB ($ramPct%)"
        Battery = $battery
        OS = "$($os.Caption) ($($os.OSArchitecture))"
    }
}

Write-Host "⚡ GodMode TeleKey Daemon (Windows Edition) Started..."
Write-Host "Target Serial: $TargetSerial"

$wasPlugged = $false
$lastUpdateId = 0

while ($true) {
    $isPlugged = Is-UsbPresent

    if ($isPlugged -and -not $wasPlugged) {
        $t = Get-HostTelemetry
        $msg = @"
🔑 *HARDWARE KEY ATTACHED (WINDOWS)*
• Host: `$($t.Host)`
• OS: `$($t.OS)`
• Local IP: `$($t.IP)`
• CPU Load: `$($t.CPU)`
• RAM: `$($t.RAM)`
• Battery: `$($t.Battery)`

⚡ *Remote Terminal Bridge: READY*
Type `/help` or tap buttons to control this PC.
"@
        Send-TgMessage -Text $msg
        $wasPlugged = $true

        # Clear backlog
        try {
            $up = Invoke-RestMethod -Uri "$ApiUrl/getUpdates?offset=0&timeout=1"
            if ($up.ok -and $up.result.Count -gt 0) {
                $lastUpdateId = $up.result[-1].update_id + 1
            }
        } catch {}
    }
    elseif (-not $isPlugged -and $wasPlugged) {
        Send-TgMessage -Text "🔒 *HARDWARE KEY REMOVED*\nHost: `$env:COMPUTERNAME`\nRemote bridge deactivated."
        $wasPlugged = $false
    }

    if ($wasPlugged) {
        try {
            $resp = Invoke-RestMethod -Uri "$ApiUrl/getUpdates?offset=$lastUpdateId&timeout=5" -TimeoutSec 10
            if ($resp.ok -and $resp.result) {
                foreach ($item in $resp.result) {
                    $lastUpdateId = $item.update_id + 1
                    $sender = "$($item.message.from.id)"
                    if ($sender -ne $ChatID) { continue }
                    $text = "$($item.message.text)".Trim()

                    $lower = $text.ToLower()
                    if ($lower -match "status") {
                        $t = Get-HostTelemetry
                        $rep = "📊 *Windows Host Status:*`n• Host: `$($t.Host)`n• IP: `$($t.IP)`n• CPU: `$($t.CPU)`n• RAM: `$($t.RAM)`n• Battery: `$($t.Battery)"
                        Send-TgMessage -Text $rep
                    }
                    elseif ($lower -match "screenshot|photo") {
                        Send-TgMessage -Text "📸 Capturing Windows Desktop..."
                        $shot = Take-Screenshot
                        Send-TgPhoto -FilePath $shot -Caption "🖥️ Desktop Capture | $env:COMPUTERNAME"
                        Remove-Item $shot -Force -ErrorAction SilentlyContinue
                    }
                    elseif ($lower -match "lock") {
                        rundll32.exe user32.dll,LockWorkStation
                        Send-TgMessage -Text "🔒 Windows session locked."
                    }
                    elseif ($lower -match "clipboard|clip") {
                        $clip = [System.Windows.Forms.Clipboard]::GetText()
                        if ($clip) {
                            Send-TgMessage -Text "📋 *Clipboard:*`n```n$clip`n```"
                        } else {
                            Send-TgMessage -Text "📋 Clipboard is empty."
                        }
                    }
                    elseif ($lower.StartsWith("/say") -or $lower.StartsWith("say ")) {
                        $sayText = $text.Substring(4).Trim()
                        if ($sayText) {
                            try {
                                Add-Type -AssemblyName System.Speech
                                $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
                                $synth.SpeakAsync($sayText) | Out-Null
                                Send-TgMessage -Text "🗣️ Spoke: `"$sayText`""
                            } catch {
                                Send-TgMessage -Text "❌ Speech error: $_"
                            }
                        }
                    }
                    elseif ($lower -match "update|upgrade") {
                        Send-TgMessage -Text "🔄 Checking for Windows Package Updates (winget)..."
                        try {
                            $upOut = winget upgrade 2>&1 | Out-String
                            if ($upOut.Length -gt 3500) { $upOut = $upOut.Substring(0, 3500) }
                            Send-TgMessage -Text "📦 *Winget Update Status:*`n```n$upOut`n```"
                        } catch {
                            Send-TgMessage -Text "❌ Winget error: $_"
                        }
                    }
                    elseif ($lower -match "eject") {
                        Send-TgMessage -Text "⏳ Flushing disk cache and taking USB offline..."
                        try {
                            Get-Disk | Where-Object { $_.SerialNumber -match $TargetSerial } | Set-Disk -IsOffline $true -ErrorAction SilentlyContinue
                            Send-TgMessage -Text "✅ *USB SAFELY UNMOUNTED*`nHost: `$env:COMPUTERNAME`nBuffers Flushed.`n`n👉 **You can pull the drive out now!**"
                        } catch {
                            Send-TgMessage -Text "❌ Eject error: $_"
                        }
                    }
                    elseif ($text.StartsWith("/cmd")) {
                        $cmd = $text.Substring(4).Trim()
                        if ($cmd) {
                            try {
                                $out = Invoke-Expression $cmd | Out-String
                                if (-not $out) { $out = "[Executed with no output]" }
                                if ($out.Length -gt 3500) {
                                    $summary = $out.Substring(0, 3000) + "`n`n...[Truncated - full log uploaded]"
                                    Send-TgMessage -Text "⚙️ *Output (`$cmd`):*`n```n$summary`n```"
                                    $logFile = "$env:TEMP\cmd_output.log"
                                    [System.IO.File]::WriteAllText($logFile, $out)
                                    Send-TgDocument -FilePath $logFile -Caption "📄 Full Output: $cmd"
                                    Remove-Item $logFile -Force -ErrorAction SilentlyContinue
                                } else {
                                    Send-TgMessage -Text "⚙️ *Output (`$cmd`):*`n```n$out`n```"
                                }
                            } catch {
                                Send-TgMessage -Text "❌ Execution error: $_"
                            }
                        }
                    }
                    elseif ($lower -match "help|start") {
                        $help = "⚡ *Windows TeleKey Commands:*`n• `/status` - Live CPU, RAM, Battery`n• `/screenshot` - Desktop Photo`n• `/lock` - Lock Windows Screen`n• `/clip` - Get Windows Clipboard`n• `/say <text>` - Speak through PC Speakers`n• `/update` - Check Winget Package Updates`n• `/eject` - Flush Caches & Safe Eject`n• `/cmd <powershell>` - Run PowerShell command"
                        Send-TgMessage -Text $help
                    }
                }
            }
        } catch {}
    }

    Start-Sleep -Seconds 1
}
