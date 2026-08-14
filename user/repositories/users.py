from user.database import users_collection
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    @staticmethod
    async def exists(username: str) -> bool:
        return await users_collection.find_one({"username": username}) is not None

    @staticmethod
    async def email_exists(email: str) -> bool:
        return await users_collection.find_one({"email": email.lower()}) is not None

    @staticmethod
    async def get_by_username(username: str):
        return await users_collection.find_one({"username": username})

    @staticmethod
    async def get_by_email(email: str):
        return await users_collection.find_one({"email": email.lower()})

    @staticmethod
    async def get_by_username_or_email(ident: str):
        ident = ident.lower()
        return await users_collection.find_one(
            {"$or": [{"username": ident}, {"email": ident}]}
        )

    @staticmethod
    async def create(doc: dict):
        await users_collection.insert_one(doc)

    @staticmethod
    async def set_password(username: str, hashed: str):
        await users_collection.update_one(
            {"username": username}, {"$set": {"hashed_password": hashed}}
        )

    @staticmethod
    async def set_email_verified(username: str, verified: bool):
        await users_collection.update_one(
            {"username": username}, {"$set": {"email_verified": verified}}
        )

    @staticmethod
    async def set_google_sub(username: str, google_sub: str):
        await users_collection.update_one(
            {"username": username}, {"$set": {"google_sub": google_sub}}
        )