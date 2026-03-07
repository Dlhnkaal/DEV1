$url = "http://localhost:8000/advertisement/predict"
$headers = @{ "Content-Type" = "application/json"; "accept" = "application/json" }

$payloads = @(
    '{"seller_id": 1, "name": "Test Item", "description": "Normal description text", "category": 1, "images_qty": 5, "item_id": 10, "is_verified_seller": true}',
    '{"seller_id": 1, "name": "Bad Item", "description": "Short", "category": 1, "images_qty": 15, "item_id": 11, "is_verified_seller": false}',
    '{"seller_id": "invalid_string", "name": "", "description": "Err", "category": 999, "images_qty": -1, "item_id": 0, "is_verified_seller": "not_a_bool"}'
)

while ($true) {
    $rand = Get-Random -Minimum 0 -Maximum 100
    if ($rand -lt 70) { $body = $payloads[0] }
    elseif ($rand -lt 90) { $body = $payloads[1] }
    else { $body = $payloads[2] }

    try {
        $response = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $body -ErrorAction SilentlyContinue
        Write-Host "." -NoNewline
    } catch {
        Write-Host "E" -NoNewline -ForegroundColor Red
    }
    
    Start-Sleep -Milliseconds 100
}
