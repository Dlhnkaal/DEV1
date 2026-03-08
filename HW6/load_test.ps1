$url_predict = "http://localhost:8000/advertisement/predict"
$url_simple = "http://localhost:8000/advertisement/simple_predict"
$headers = @{ "Content-Type" = "application/json"; "accept" = "application/json" }

$payloads = @(
    '{"seller_id": 1, "name": "Test Item", "description": "Normal description text", "category": 1, "images_qty": 5, "item_id": 10, "is_verified_seller": true}',
    '{"seller_id": 1, "name": "Test Item", "description": "Normal description text", "category": 1, "images_qty": 0, "item_id": 10, "is_verified_seller": false}',
    '{"seller_id": 1, "name": "Bad Item", "description": "Short", "category": 1, "images_qty": 15, "item_id": 11, "is_verified_seller": false}',
    '{"seller_id": "invalid_string", "name": "", "description": "Err", "category": 999, "images_qty": -1, "item_id": 0, "is_verified_seller": "not_a_bool"}'
)

while ($true) {
    $rand_payload = Get-Random -Minimum 0 -Maximum 100
    if ($rand_payload -lt 70) { $body = $payloads[0] }
    elseif ($rand_payload -lt 90) { $body = $payloads[1] }
    else { $body = $payloads[2] }

    $rand_url = Get-Random -Minimum 0 -Maximum 100
    if ($rand_url -lt 50) { $current_url = $url_predict }
    else { $current_url = $url_simple }

    try {
        $response = Invoke-RestMethod -Uri $current_url -Method Post -Headers $headers -Body $body -ErrorAction SilentlyContinue
        Write-Host "." -NoNewline
    } catch {
        Write-Host "E" -NoNewline -ForegroundColor Red
    }
    
    Start-Sleep -Milliseconds 100
}