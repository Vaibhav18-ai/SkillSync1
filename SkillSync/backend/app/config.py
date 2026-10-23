from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives in the project root: C:\SkillSync\.env
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    model_config = SettingsConfigDict(env_file=ENV_FILE)

settings = Settings()