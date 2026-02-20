import pytest
from fastapi import status
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from models.moderation import ModerationResultInDB
from errors import AdvertisementNotFoundError, ModerationTaskNotFoundError


@pytest.mark.integration
@pytest.mark.asyncio
class TestModerationAPI:

    @pytest.mark.parametrize("item_id, expected_status", [
        (999, status.HTTP_404_NOT_FOUND),
        (888, status.HTTP_404_NOT_FOUND)])
    async def test_create_task_not_found(self, async_client, item_id, expected_status):
        client, mock_service = async_client
        mock_service.start_moderation.side_effect = AdvertisementNotFoundError(f"Ad {item_id} not found")
        
        response = await client.post("/moderation/async_predict", json={"item_id": item_id})
        assert response.status_code == expected_status

    @pytest.mark.parametrize("item_id", [-1, 0, "abc", None])
    async def test_create_task_validation_error(self, async_client, item_id):
        client, _ = async_client
        response = await client.post("/moderation/async_predict", json={"item_id": item_id})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize("task_id, db_status, is_violation, probability", [
        (123, "completed", True, 0.95),
        (124, "completed", False, 0.05),
        (125, "pending", None, None)])
    async def test_get_moderation_result_success(self, async_client, task_id, db_status, is_violation, probability):
        client, mock_service = async_client
        mock_data = ModerationResultInDB(
            id=task_id,
            item_id=55,
            status=db_status,
            is_violation=is_violation,
            probability=probability,
            created_at="2024-01-01T00:00:00",
            processed_at="2024-01-01T00:00:01" if db_status == "completed" else None
        )
        mock_service.get_moderation_status.return_value = mock_data
        
        response = await client.get(f"/moderation/moderation_result/{task_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == db_status
        assert data["is_violation"] == is_violation
        assert data["probability"] == probability

    @pytest.mark.parametrize("task_id", [555, 777, 1000])
    async def test_get_moderation_result_not_found(self, async_client, task_id):
        client, mock_service = async_client
        mock_service.get_moderation_status.side_effect = ModerationTaskNotFoundError("Task not found")
        
        response = await client.get(f"/moderation/moderation_result/{task_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND