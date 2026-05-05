import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str
    pool_size: int = 5
    max_overflow: int = 10

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


PRIMARY_DB = DatabaseConfig(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    name=os.getenv("DB_NAME", "pricing_engine"),
    user=os.getenv("DB_USER", "pricing_user"),
    password=os.getenv("DB_PASSWORD", ""),
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
)

REDIS_CONFIG: dict = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")),
    "password": os.getenv("REDIS_PASSWORD") or None,
}
