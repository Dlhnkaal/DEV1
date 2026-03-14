import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import Request
from dependencies import get_current_account, get_ml_service, get_moderation_service
from models.account import AccountModel
from errors import UnauthorizedError


def _mock_request(cookie_value=None) -> MagicMock:
    req = MagicMock(spec=Request)
    req.cookies.get.return_value = cookie_value
    return req


class TestGetCurrentAccount:

    async def test_no_cookie_raises_unauthorized(self):
        req = _mock_request(cookie_value=None)
        auth_srv = AsyncMock()

        with pytest.raises(UnauthorizedError):
            await get_current_account(req, auth_srv)

        auth_srv.verify.assert_not_called()

    @pytest.mark.parametrize("token", ["bad_token", "expired_token", "tampered"])
    async def test_invalid_token_raises_unauthorized(self, token):
        req = _mock_request(cookie_value=token)
        auth_srv = AsyncMock()
        auth_srv.verify.side_effect = UnauthorizedError()

        with pytest.raises(UnauthorizedError):
            await get_current_account(req, auth_srv)

        auth_srv.verify.assert_awaited_once_with(token)

    async def test_valid_token_returns_account(self):
        req = _mock_request(cookie_value="valid_token")
        expected = AccountModel(id=1, login="user", password="password123", is_blocked=False)
        auth_srv = AsyncMock()
        auth_srv.verify.return_value = expected

        result = await get_current_account(req, auth_srv)

        assert result == expected
        auth_srv.verify.assert_awaited_once_with("valid_token")

    async def test_blocked_account_raises_unauthorized(self):
        req = _mock_request(cookie_value="blocked_token")
        auth_srv = AsyncMock()
        auth_srv.verify.side_effect = UnauthorizedError()

        with pytest.raises(UnauthorizedError):
            await get_current_account(req, auth_srv)


class TestGetMlService:

    def test_returns_service_from_app_state(self):
        req = MagicMock(spec=Request)
        mock_svc = MagicMock()
        req.app.state.ml_service = mock_svc

        assert get_ml_service(req) is mock_svc


class TestGetModerationService:

    def test_returns_service_from_app_state(self):
        req = MagicMock(spec=Request)
        mock_svc = MagicMock()
        req.app.state.moderation_service = mock_svc

        assert get_moderation_service(req) is mock_svc