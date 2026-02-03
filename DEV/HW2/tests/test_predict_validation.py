def test_predict_validation_error(client):
    response = client.post(
        "/predict",
        json={
            "seller_id": "abc"
        },
    )

    assert response.status_code == 422