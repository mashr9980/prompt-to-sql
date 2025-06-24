import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..config import settings
from ..core.exceptions import LLMServiceError, ConfigurationError

logger = logging.getLogger(__name__)


class LLMService(ABC):
    
    @abstractmethod
    def generate_sql(self, natural_language_query: str, table_info: str) -> str:
        pass


class OllamaLLMService(LLMService):
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        
        try:
            # Test if ollama package is available
            import ollama
            self.client = ollama.Client(host=self.base_url)
            
            # Test connection to Ollama
            try:
                models = self.client.list()
                logger.info(f"Ollama LLM service initialized successfully with {len(models.get('models', []))} models")
                
                # Check if our model is available
                # model_names = [m.get('name', '') for m in models.get('models', [])]
                # if not any(self.model in name for name in model_names):
                #     logger.warning(f"Model {self.model} not found in available models: {model_names}")
                #     logger.warning("Make sure to run: ollama pull qwen2.5:7b")
                    
            except Exception as e:
                logger.warning(f"Could not connect to Ollama server: {e}")
                logger.warning("Make sure Ollama is running on http://localhost:11434")
                
        except ImportError:
            raise ConfigurationError("Ollama package not installed. Run: pip install ollama")
        except Exception as e:
            raise LLMServiceError(f"Failed to initialize Ollama client: {str(e)}")
    
    def generate_sql(self, natural_language_query: str, table_info: str) -> str:
        logger.info("Note: LLM service is now handled by LangChain SQL Agent in TextToSQLService")
        return "This method is deprecated - use LangChain SQL Agent instead"


class OpenAILLMService(LLMService):
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        
        if not self.api_key:
            raise ConfigurationError("OpenAI API key not configured")
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            logger.info("OpenAI LLM service initialized successfully")
        except ImportError:
            raise ConfigurationError("OpenAI package not installed. Run: pip install openai")
        except Exception as e:
            raise LLMServiceError(f"Failed to initialize OpenAI client: {str(e)}")
    
    def generate_sql(self, natural_language_query: str, table_info: str) -> str:
        logger.info("Note: LLM service is now handled by LangChain SQL Agent in TextToSQLService")
        return "This method is deprecated - use LangChain SQL Agent instead"


class GeminiLLMService(LLMService):
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ConfigurationError("Gemini API key not configured")
        logger.info("Gemini LLM service initialized (placeholder)")
    
    def generate_sql(self, natural_language_query: str, table_info: str) -> str:
        raise NotImplementedError("Gemini LLM service not yet implemented")


def create_llm_service(service_type: str = None) -> LLMService:
    if service_type is None:
        service_type = settings.DEFAULT_LLM_PROVIDER
    
    service_type = service_type.lower()
    
    if service_type == "ollama":
        return OllamaLLMService()
    elif service_type == "openai":
        return OpenAILLMService()
    elif service_type == "gemini":
        return GeminiLLMService()
    else:
        raise ConfigurationError(f"Unsupported LLM service type: {service_type}")