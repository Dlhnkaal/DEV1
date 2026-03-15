import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

from workers.moderation_worker import ModerationWorker
from errors import AdvertisementNotFoundError
from models.advertisement import PredictionResult


class MockConsumer:

    def __init__(self, messages):
        self._messages = messages
        self.commit = AsyncMock()

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for msg in self._messages:
            yield msg

    async def stop(self):
        pass


def _msg(moderation_id: int, item_id: int) -> MagicMock:
    m = MagicMock()
    m.value = {"moderation_id": moderation_id, "item_id": item_id,
               "timestamp": "2024-01-01T00:00:00"}
    return m


def _make_worker(*messages) -> ModerationWorker:
    worker = ModerationWorker()
    worker.consumer = MockConsumer(list(messages))
    worker.dlq_producer = AsyncMock()
    worker.ml_service = AsyncMock()
    worker.moderation_repo = AsyncMock()
    return worker


class TestWorkerSuccessScenario:

    @pytest.mark.parametrize("is_violation,probability", [
        (True, 0.9),
        (False, 0.1),
    ])
    async def test_success_processes_and_commits(self, is_violation, probability):
        worker = _make_worker(_msg(1, 10))
        worker.ml_service.simple_predict.return_value = PredictionResult(
            is_violation=is_violation, probability=probability
        )

        with patch.object(worker, 'start', new=AsyncMock()), \
             patch.object(worker, 'stop', new=AsyncMock()):
            await worker.consume()

        worker.moderation_repo.update_result.assert_awaited_once_with(
            task_id=1,
            status="completed",
            is_violation=is_violation,
            probability=probability,
            error_message=None,
        )
        worker.consumer.commit.assert_awaited_once()


class TestWorkerDLQScenarios:

    async def test_advertisement_not_found_goes_to_dlq_no_retry(self):
        worker = _make_worker(_msg(2, 999))
        worker.ml_service.simple_predict.side_effect = AdvertisementNotFoundError("not found")

        with patch.object(worker, 'start', new=AsyncMock()), \
             patch.object(worker, 'stop', new=AsyncMock()), \
             patch.object(worker, 'process_dlq', new=AsyncMock()) as mock_dlq:
            await worker.consume()

        assert worker.ml_service.simple_predict.call_count == 1
        mock_dlq.assert_awaited_once()
        worker.consumer.commit.assert_awaited_once()

    async def test_all_retries_exhausted_goes_to_dlq(self):
        worker = _make_worker(_msg(4, 10))
        worker.MAX_RETRIES = 3
        worker.ml_service.simple_predict.side_effect = Exception("persistent error")

        with patch.object(worker, 'start', new=AsyncMock()), \
             patch.object(worker, 'stop', new=AsyncMock()), \
             patch.object(worker, 'process_dlq', new=AsyncMock()) as mock_dlq, \
             patch('workers.moderation_worker.asyncio.sleep', new=AsyncMock()):
            await worker.consume()

        assert worker.ml_service.simple_predict.call_count == 3
        mock_dlq.assert_awaited_once()
        worker.consumer.commit.assert_awaited_once()


class TestWorkerRetryScenario:

    async def test_transient_error_retries_then_succeeds(self):
        worker = _make_worker(_msg(3, 10))
        worker.ml_service.simple_predict.side_effect = [
            Exception("transient error"),
            PredictionResult(is_violation=False, probability=0.2),
        ]

        with patch.object(worker, 'start', new=AsyncMock()), \
             patch.object(worker, 'stop', new=AsyncMock()), \
             patch('workers.moderation_worker.asyncio.sleep', new=AsyncMock()):
            await worker.consume()

        assert worker.ml_service.simple_predict.call_count == 2
        worker.moderation_repo.update_result.assert_awaited_once_with(
            task_id=3,
            status="completed",
            is_violation=False,
            probability=0.2,
            error_message=None,
        )
        worker.consumer.commit.assert_awaited_once()


class TestWorkerInvalidMessage:

    @pytest.mark.parametrize("data", [
        {"item_id": 10},
        {"moderation_id": 1},
        {},
    ])
    async def test_invalid_format_is_skipped(self, data):
        msg = MagicMock()
        msg.value = data
        worker = _make_worker(msg)

        with patch.object(worker, 'start', new=AsyncMock()), \
             patch.object(worker, 'stop', new=AsyncMock()):
            await worker.consume()

        worker.ml_service.simple_predict.assert_not_called()
        worker.consumer.commit.assert_awaited_once()