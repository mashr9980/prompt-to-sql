import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_TITLE: str = "Text-to-SQL API"
    API_VERSION: str = "1.0.0"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    DATABASE_URL: str = os.getenv("DATABASE_URL","")

    # DATABASE_URL: str = (
    #     "mssql+pyodbc://sa:Esap.12.Three@176.9.16.194,1433/"
    #     "JustForRestore?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=no&timeout=30"
    # )
    
    DEFAULT_LLM_PROVIDER: str = "gemini"
    
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_TEMPERATURE: float = 0.0
    OLLAMA_MAX_TOKENS: int = 4000
    
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY","")
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.0
    OPENAI_MAX_TOKENS: int = 4000
    
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_TEMPERATURE: float = 0.0
    GEMINI_MAX_TOKENS: int = 4000
    
    CACHE_TTL: int = 300
    SCHEMA_CACHE_TTL: int = 1800
    
    CONNECTION_TIMEOUT: int = 300
    QUERY_TIMEOUT: int = 60
    MAX_RETRIES: int = 3
    
    CORS_ORIGINS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()