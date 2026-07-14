from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

Base = declarative_base()
engine = create_async_engine(
    url = os.getenv('DB_URL'),
    echo=True
)
asyncSession = async_sessionmaker(bind=engine, autocommit=False, autoflush=False)

async def getDB():
    dbSession = asyncSession()
    try:
        yield dbSession
    finally:
        await dbSession.close()
