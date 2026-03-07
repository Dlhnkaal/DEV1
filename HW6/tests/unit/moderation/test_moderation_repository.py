import pytest
from datetime import datetime
from unittest.mock import AsyncMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from models.moderation import ModerationResultInDB, TaskIdList
from repositories.moderation import ModerationRepository, ModerationPostgresStorage, ModerationRedisStorage


@pytest.mark.asyncio
class TestModerationRepository:

    async def test_get_result_by_id_cache_hit(self):
        redis_storage = AsyncMock(spec=ModerationRedisStorage)
        pg_storage = AsyncMock(spec=ModerationPostgresStorage)

        cached_data = {
            "id": 1,
            "item_id": 10,
            "status": "completed",
            "is_violation": True,
            "probability": 0.95,
            "error_message": None,
            "created_at": datetime.now(),
            "processed_at": datetime.now()
        }
        redis_storage.get.return_value = cached_data

        repo = ModerationRepository(storage=pg_storage, redis_storage=redis_storage)
        dto = AsyncMock(task_id=1)
        result = await repo.get_result_by_id(dto)

        assert isinstance(result, ModerationResultInDB)
        assert result.id == 1
        redis_storage.get.assert_called_once_with(1)
        pg_storage.get_by_id.assert_not_called()

    async def test_get_result_by_id_cache_miss(self):
        redis_storage = AsyncMock(spec=ModerationRedisStorage)
        pg_storage = AsyncMock(spec=ModerationPostgresStorage)

        redis_storage.get.return_value = None
        raw_data = {
            "id": 2,
            "item_id": 20,
            "status": "pending",
            "is_violation": None,
            "probability": None,
            "error_message": None,
            "created_at": datetime.now(),
            "processed_at": None
        }
        pg_storage.get_by_id.return_value = raw_data

        repo = ModerationRepository(storage=pg_storage, redis_storage=redis_storage)
        dto = AsyncMock(task_id=2)
        result = await repo.get_result_by_id(dto)

        assert isinstance(result, ModerationResultInDB)
        assert result.id == 2
        redis_storage.get.assert_called_once_with(2)
        pg_storage.get_by_id.assert_called_once_with(2)
        redis_storage.set.assert_called_once_with(2, raw_data)

    async def test_get_result_by_id_not_found(self):
        redis_storage = AsyncMock(spec=ModerationRedisStorage)
        pg_storage = AsyncMock(spec=ModerationPostgresStorage)

        redis_storage.get.return_value = None
        pg_storage.get_by_id.return_value = None

        repo = ModerationRepository(storage=pg_storage, redis_storage=redis_storage)
        dto = AsyncMock(task_id=999)
        result = await repo.get_result_by_id(dto)

        assert result is None

    async def test_update_result_invalidates_cache(self):
        redis_storage = AsyncMock(spec=ModerationRedisStorage)
        pg_storage = AsyncMock(spec=ModerationPostgresStorage)

        repo = ModerationRepository(storage=pg_storage, redis_storage=redis_storage)
        dto = AsyncMock(task_id=3)
        update_data = AsyncMock(status="completed", is_violation=False, probability=0.1, error_message=None)

        await repo.update_result(dto, update_data)

        pg_storage.update_result.assert_called_once_with(
            task_id=3,
            status=update_data.status,
            is_violation=update_data.is_violation,
            probability=update_data.probability,
            error_message=update_data.error_message
        )
        redis_storage.delete.assert_called_once_with(3)

    async def test_get_task_ids_by_item_id_returns_dto(self):
        pg_storage = AsyncMock(spec=ModerationPostgresStorage)
        pg_storage.get_task_ids_by_item_id.return_value = [1, 2, 3]

        repo = ModerationRepository(storage=pg_storage)
        result = await repo.get_task_ids_by_item_id(100)

        assert isinstance(result, TaskIdList)
        assert result.task_ids == [1, 2, 3]

    async def test_delete_from_cache_by_item_id(self):
        redis_storage = AsyncMock(spec=ModerationRedisStorage)
        pg_storage = AsyncMock(spec=ModerationPostgresStorage)

        repo = ModerationRepository(storage=pg_storage, redis_storage=redis_storage)
        repo.get_task_ids_by_item_id = AsyncMock(return_value=TaskIdList(task_ids=[5, 6, 7]))

        await repo.delete_from_cache_by_item_id(200)

        repo.get_task_ids_by_item_id.assert_called_once_with(200)
        redis_storage.delete.assert_any_call(5)
        redis_storage.delete.assert_any_call(6)
        redis_storage.delete.assert_any_call(7)
        assert redis_storage.delete.call_count == 3