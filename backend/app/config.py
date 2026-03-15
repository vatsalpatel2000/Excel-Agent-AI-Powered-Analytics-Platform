"""
Configuration Settings - Unified Excel Agent Backend

Azure-ready configuration with environment variable support.
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with Azure-ready defaults - Production Grade."""
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4.1"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    OPENAI_MAX_TOKENS: int = 32000  # Maximum output capacity
    TEMPERATURE: float = 0.0  # Deterministic responses
    
    # Agent Configuration - Production Grade
    MAX_ITERATIONS: int = 100000  # Extended reasoning capability
    MAX_CONTEXT_MESSAGES: int = 500  # More conversation context
    MAX_RESULT_ROWS_FOR_LLM: int = 5000  # Maximum rows to send to LLM
    
    # Advanced Statistical Analysis
    ENABLE_ADVANCED_STATS: bool = True
    STATS_CONFIDENCE_LEVEL: float = 0.98
    
    # Session Persistence
    SESSION_PERSISTENCE_ENABLED: bool = True
    SESSION_CACHE_DIR: str = "./session_cache"
    
    # File Processing
    MAX_FILE_SIZE_MB: int = 100  # Increased for larger files
    UPLOAD_DIR: str = "./uploads"
    EXPORT_DIR: str = "./exports"
    
    # Redis Configuration (for future Azure Redis integration)
    REDIS_URL: Optional[str] = None
    REDIS_ENABLED: bool = False
    
    # Azure SQL (for future integration)
    DATABASE_URL: Optional[str] = None
    
    # Azure Blob Storage (for future integration)
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = None
    
    # Azure AI Search (for future vector search integration)
    AZURE_SEARCH_ENDPOINT: Optional[str] = None
    AZURE_SEARCH_KEY: Optional[str] = None
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    
    # Backend URL for download links (used in export tool)
    BACKEND_URL: str = "http://localhost:8000"
    
    # CORS - stored as comma-separated string
    CORS_ORIGINS_STR: str = "http://localhost:3000,http://localhost:5173"
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",") if origin.strip()]
    
    @property
    def SUPPORTED_EXTENSIONS(self) -> List[str]:
        """Supported file extensions."""
        return [".csv", ".xls", ".xlsx", ".xlsm"]
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
