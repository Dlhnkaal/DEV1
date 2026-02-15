import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import app
from models.moderation import (
    AsyncPredictionResponse, 
    ModerationResultInDB
)
from workers.moderation_worker import ModerationWorker
from errors import AdvertisementNotFoundError, ModerationTaskNotFoundError

@pytest.mark.asyncio
@pytest.mark.parametrize("item_id, expected_status", [
    (999, status.HTTP_404_NOT_FOUND),
    (888, status.HTTP_404_NOT_FOUND)])
async def test_create_task_not_found(async_client, item_id, expected_status): 
    client, mock_service = async_client
    
    mock_service.start_moderation.side_effect = AdvertisementNotFoundError(f"Ad {item_id} not found")
    
    response = await client.post("/moderation/async_predict", json={"item_id": item_id})
    
    assert response.status_code == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize("item_id", [-1, 0, "abc", None])
async def test_create_task_validation_error(async_client, item_id):
    client, _ = async_client
    response = await client.post("/moderation/async_predict", json={"item_id": item_id})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT 


@pytest.mark.asyncio
@pytest.mark.parametrize("task_id, db_status, is_violation, probability", [
    (123, "completed", True, 0.95),
    (124, "completed", False, 0.05),
    (125, "pending", None, None)])
async def test_get_moderation_result_success(
    async_client, task_id, db_status, is_violation, probability):
    client, mock_service = async_client
    
    mock_data = ModerationResultInDB(
        id=task_id, 
        item_id=55,
        status=db_status, 
        is_violation=is_violation, 
        probability=probability,
        created_at="2024-01-01T00:00:00"    )
    mock_service.get_moderation_status.return_value = mock_data
    
    response = await client.get(f"/moderation/moderation_result/{task_id}")
    
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["status"] == db_status
    assert data["is_violation"] == is_violation
    assert data["probability"] == probability


@pytest.mark.asyncio
@pytest.mark.parametrize("task_id", [555, 777, 1000])
async def test_get_moderation_result_not_found(async_client, task_id):
    client, mock_service = async_client
    mock_service.get_moderation_status.side_effect = ModerationTaskNotFoundError("Task not found")
    
    response = await client.get(f"/moderation/moderation_result/{task_id}")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.fixture
def mock_worker_deps():
    with patch("workers.moderation_worker.AdvertisementMLService") as MockML, \
         patch("workers.moderation_worker.ModerationRepository") as MockRepo, \
         patch("workers.moderation_worker.ModerationProducer") as MockDLQ, \
         patch("workers.moderation_worker.AIOKafkaConsumer") as MockConsumer:
        
        ml_service = MockML.return_value
        ml_service.simple_predict = AsyncMock()
        
        repo = MockRepo.return_value
        repo.update_result = AsyncMock()
        
        dlq = MockDLQ.return_value
        dlq.send_message = AsyncMock()
        dlq.start = AsyncMock()
        dlq.stop = AsyncMock()
        
        consumer = MockConsumer.return_value
        consumer.start = AsyncMock()
        consumer.stop = AsyncMock()
        consumer.commit = AsyncMock()
        
        worker = ModerationWorker()
        worker.ml_service = ml_service
        worker.moderation_repo = repo
        worker.dlq_producer = dlq
        worker.consumer = consumer 
        
        yield worker, ml_service, repo, dlq, consumer


@pytest.mark.asyncio
@pytest.mark.parametrize("predict_result, expected_status, expected_violation", [
    ((False, 0.1), "completed", False),
    ((True, 0.99), "completed", True)])
async def test_worker_process_success(
    mock_worker_deps, predict_result, expected_status, expected_violation):
    worker, ml_service, repo, dlq, consumer = mock_worker_deps
    
    ml_service.simple_predict.return_value = predict_result
    
    mock_msg = MagicMock()
    mock_msg.value = {"moderation_id": 100, "item_id": 5}
    
    async def async_msg_gen():
        yield mock_msg
    
    consumer.__aiter__ = lambda *args: async_msg_gen()
    
    await worker.consume()
    
    repo.update_result.assert_awaited_once()
    call_kwargs = repo.update_result.call_args[1]
    update_dto = call_kwargs["update_data"]
    
    assert update_dto.status == expected_status
    assert update_dto.is_violation == expected_violation
    
    consumer.commit.assert_awaited_once()
    dlq.start.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("error_msg, retry_count", [
    ("ML Service Timeout", 3),
    ("Connection Refused", 3)])
async def test_worker_retry_dlq(mock_worker_deps, error_msg, retry_count):
    worker, ml_service, repo, dlq, consumer = mock_worker_deps
    worker.RETRY_DELAY = 0.001
    
    ml_service.simple_predict.side_effect = Exception(error_msg)
    
    mock_msg = MagicMock()
    mock_msg.value = {"moderation_id": 200, "item_id": 5}
    
    async def async_msg_gen():
        yield mock_msg
        
    consumer.__aiter__ = lambda *args: async_msg_gen()
    
    await worker.consume()
    
    assert ml_service.simple_predict.await_count == retry_count
    dlq.send_message.assert_awaited_once()
    
    call_args = dlq.send_message.call_args
    sent_message = call_args[0][1]
    assert sent_message["error"] == error_msg
    
    consumer.commit.assert_awaited()