from dataclasses import dataclass
from models.users import UserModel
from typing import Mapping
from typing import Any
from typing import Sequence
from uuid import uuid4
from models.users import UserModel
from errors import UserNotFoundError


_COLLECTION: list[Mapping[str, Any]] = []


@dataclass(frozen=True)
class UserStorage:

    async def create(self, **values: Mapping[str, Any]) -> Mapping[str, Any]:
        user = dict(
            id=str(uuid4()),
            **values,
        )
        _COLLECTION.append(user)

        return user


    async def get_by_name_and_password(self, name: str, password: str) -> Mapping[str, Any]:
        users = [
            user
            for user
            in _COLLECTION
            if user['name'] == name and user['password'] == password
        ]
        
        if not users:
            raise UserNotFoundError() 

        return users[0]
    

    async def get(self, user_id: str) -> Mapping[str, Any]:
        user = await self._get_user_by_id(user_id)
        return user


    async def get_many(self) -> Sequence[Mapping[str, Any]]:
        return _COLLECTION


    async def delete(self, user_id: str) -> Mapping[str, Any]:
        user = await self._get_user_by_id(user_id)

        index = _COLLECTION.index(user)
        del _COLLECTION[index]

        return user


    async def update(self, user_id: str, **changes: Mapping[str, Any]) -> Mapping[str, Any]:
        user = await self._get_user_by_id(user_id)

        for key, value in changes.items():
            user[key] = value

        return user
    

    async def _get_user_by_id(self, user_id: str) -> UserModel:
        users = [user for user in _COLLECTION if user['id'] == user_id]

        if not users:
            raise UserNotFoundError()

        return users[0]


@dataclass(frozen=True)
class UserRepository:
    user_storage: UserStorage = UserStorage()


    async def create(self, name: str, password: str, email: str) -> UserModel:
        raw_user = await self.user_storage.create(
            name=name,
            password=password,
            email=email,
        )
        return UserModel(**raw_user)


    async def get_by_name_and_password(self, name: str, password: str) -> UserModel:
        raw_user = await self.user_storage.get_by_name_and_password(name, password)
        return UserModel(**raw_user)
    

    async def get(self, user_id: str) -> UserModel:
        raw_user = await self.user_storage.get(user_id)
        return UserModel(**raw_user)


    async def delete(self, user_id: str) -> UserModel:
        raw_user = await self.user_storage.delete(user_id)
        return UserModel(**raw_user)


    async def update(self, user_id: str, **changes: Mapping[str, Any]) -> UserModel:
        raw_user = await self.user_storage.update(user_id, **changes)
        return UserModel(**raw_user)
    

    async def get_many(self) -> Sequence[UserModel]:
        return [
            UserModel(**raw_user)
            for raw_user
            in await self.user_storage.get_many()
        ]
