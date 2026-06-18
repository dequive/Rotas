
 = Get-Content -Path 'c:\Users\Quive\OneDrive\Documents\Rotas\.planning\research\STACK.md' -Raw
 = @{content = 'PLACEHOLDER'}
 = [System.Text.Json.JsonSerializer]::Serialize()
Set-Content -Path 'c:\Users\Quive\OneDrive\Documents\Rotas\summary_data.json' -Value  -Encoding utf8
Write-Host 'done'
