from main import app


def test_model_unavailable(client):
    app.state.model = None

    response = client.post(
        "/predict",
        json={
            "seller_id": 1,
            "is_verified_seller": False,
            "item_id": 10,
            "name": "Item",
            "description": "Desc",
            "category": 1,
            "images_qty": 1,
        },
    )

    assert response.status_code == 503