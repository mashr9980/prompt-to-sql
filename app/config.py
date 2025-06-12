import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Configuration
    API_TITLE: str = "Text-to-SQL API"
    API_VERSION: str = "1.0.0"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Database Configuration
    DATABASE_URL: str = (
        "mssql+pyodbc://sa:Esap.12.Three@176.9.16.194,1433/"
        "JustForRestore?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=no&timeout=30"
    )
    
    # Alternative connection strings for fallback
    # DATABASE_FALLBACK_URLS: List[str] = [
    #     # "mssql+pyodbc://sa:Esap.12.Three@176.9.16.194,1433/JustForRestore?driver=SQL+Server&TrustServerCertificate=yes&timeout=30",
    #     "mssql+pyodbc://sa:Esap.12.Three@176.9.16.194,1433/JustForRestore?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=no&timeout=30"
    # ]
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.0
    OPENAI_MAX_TOKENS: int = 1000
    
    # Gemini Configuration (for future use)
    # GEMINI_API_KEY: str = "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"
    
    # Cache Configuration
    CACHE_TTL: int = 300
    SCHEMA_CACHE_TTL: int = 1800
    
    # Performance Configuration
    CONNECTION_TIMEOUT: int = 30
    QUERY_TIMEOUT: int = 60
    MAX_RETRIES: int = 3
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()