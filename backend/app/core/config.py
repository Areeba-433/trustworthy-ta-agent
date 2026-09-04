from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@localhost/tta_db"
    SECRET_KEY: str   = "your-secret-key-change-in-production"
    ALGORITHM: str    = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES:        int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES:       int = 10080
    REMEMBER_ME_ACCESS_EXPIRE_MINUTES:  int = 10080
    REMEMBER_ME_REFRESH_EXPIRE_MINUTES: int = 43200
    SESSION_INACTIVITY_MINUTES:         int = 30

    # Pydantic V2 syntax — class Config deprecated
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()