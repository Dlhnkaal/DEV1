import pytest
from unittest.mock import AsyncMock, patch
from repositories.user import UserRepository
from repositories.advertisement import AdvertisementRepository
from models.user import UserCreate
from models.advertisement import AdvertisementCreate
from errors import UserNotFoundError, AdvertisementNotFoundError

@pytest.mark.asyncio
async def test_user_repository_create():
    mock_connection = AsyncMock()
    mock_row = {'id':1, 'name':'Test User', 'email':'test@example.com', 'is_verified_seller':True, 'created_at':'2024-01-01T00:00:00'}
    mock_connection.fetchrow.return_value = mock_row
    with patch('repositories.user.get_pg_connection') as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_connection
        repo = UserRepository()
        user_data = UserCreate(name='Test User', email='test@example.com', is_verified_seller=True, password='password123')
        result = await repo.create(user_data)
        assert result.id == 1
        assert result.name == 'Test User'
        assert result.email == 'test@example.com'
        assert result.is_verified_seller == True

@pytest.mark.asyncio
async def test_user_repository_get_by_id():
    mock_connection = AsyncMock()
    mock_row = {'id':1, 'name':'Test User', 'email':'test@example.com', 'is_verified_seller':False, 'created_at':'2024-01-01T00:00:00'}
    mock_connection.fetchrow.return_value = mock_row
    with patch('repositories.user.get_pg_connection') as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_connection
        repo = UserRepository()
        result = await repo.get_by_id(1)
        assert result.id == 1
        assert result.name == 'Test User'

@pytest.mark.asyncio
async def test_user_repository_get_by_id_not_found():
    mock_connection = AsyncMock()
    mock_connection.fetchrow.return_value = None
    with patch('repositories.user.get_pg_connection') as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_connection
        repo = UserRepository()
        with pytest.raises(UserNotFoundError):
            await repo.get_by_id(999)

@pytest.mark.asyncio
async def test_advertisement_repository_create():
    mock_connection = AsyncMock()
    mock_row = {'id':1, 'seller_id':1, 'name':'Test Item', 'description':'Test description', 'category':5, 'images_qty':3, 'created_at':'2024-01-01T00:00:00', 'updated_at':'2024-01-01T00:00:00'}
    mock_connection.fetchrow.return_value = mock_row
    with patch('repositories.advertisement.get_pg_connection') as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_connection
        repo = AdvertisementRepository()
        ad_data = AdvertisementCreate(seller_id=1, name='Test Item', description='Test description', category=5, images_qty=3)
        result = await repo.create(ad_data)
        assert result.id == 1
        assert result.seller_id == 1
        assert result.name == 'Test Item'
        assert result.category == 5

@pytest.mark.asyncio
async def test_advertisement_repository_get_by_id():
    mock_connection = AsyncMock()
    mock_row = {'id':1, 'seller_id':1, 'name':'Test Item', 'description':'Test description', 'category':5, 'images_qty':3, 'created_at':'2024-01-01T00:00:00', 'updated_at':'2024-01-01T00:00:00', 'is_verified_seller':True}
    mock_connection.fetchrow.return_value = mock_row
    with patch('repositories.advertisement.get_pg_connection') as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_connection
        repo = AdvertisementRepository()
        result = await repo.get_by_id(1)
        assert result.id == 1
        assert result.seller_id == 1
        assert result.is_verified_seller == True
        assert result.category == 5

@pytest.mark.asyncio
async def test_advertisement_repository_get_by_id_not_found():
    mock_connection = AsyncMock()
    mock_connection.fetchrow.return_value = None
    with patch('repositories.advertisement.get_pg_connection') as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_connection
        repo = AdvertisementRepository()
        with pytest.raises(AdvertisementNotFoundError):
            await repo.get_by_id(999)