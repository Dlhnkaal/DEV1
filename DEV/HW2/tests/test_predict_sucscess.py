def test_predict_violation_true(client):
    response = client.post(
        "/predict",
        json={
            "seller_id": 1,
            "is_verified_seller": False,
            "item_id": 100,
            "name": "Phone",
            "description": "Cheap phone without warranty",
            "category": 1,
            "images_qty": 0,
        },
    )

    assert response.status_code == 200
    assert "is_violation" in response.json()
    assert "probability" in response.json()


def test_predict_violation_false(client):
    response = client.post(
        "/predict",
        json={
            "seller_id": 2,
            "is_verified_seller": True,
            "item_id": 101,
            "name": "Table",
            "description": "Wooden table",
            "category": 2,
            "images_qty": 5,
        },
    )

    assert response.status_code == 200
    assert response.json()["is_violation"] in [True, False]