"""
    this file is used to setup communication with the database by exposing a function that every route uses to request and return a database connection
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

Base = declarative_base() # create a base class which models will inherit from
engine = create_async_engine(
    url = os.getenv('DB_URL'),
    echo=True # print each SQL atatement for debugging
) # object to manage the connection pool to postgres
asyncSession = async_sessionmaker(bind=engine, autocommit=False, autoflush=False) # manage sessions bound to the same engine object

async def getDB():
    dbSession = asyncSession() # create a new session with the database
    try:
        yield dbSession # hand the session to the route that requested it and pause execution as route runs its code
    finally:
        await dbSession.close() # close session after route completes
