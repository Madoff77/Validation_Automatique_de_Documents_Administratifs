from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from api.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_client: AsyncIOMotorClient = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


async def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongo_db]


async def connect():
    global _client
    _client = AsyncIOMotorClient(settings.mongo_uri)
    # Vérification connexion
    await _client.admin.command("ping")
    logger.info("mongodb_connected", uri=settings.mongo_uri, db=settings.mongo_db)


async def disconnect():
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("mongodb_disconnected")
