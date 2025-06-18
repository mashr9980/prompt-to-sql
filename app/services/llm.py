import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..config import settings
from ..core.exceptions import ConfigurationError, LLMServiceError

logger = logging.getLogger(__name__)


class LLMService(ABC):

    @abstractmethod
    def generate_sql(self, natural_language_query: str, table_info: str) -> str:
        pass


# class OpenAILLMService(LLMService):

#     def __init__(self, api_key: Optional[str] = None):
#         self.api_key = api_key or settings.OPENAI_API_KEY

#         if not self.api_key:
#             raise ConfigurationError("OpenAI API key not configured")

#         try:
#             from openai import OpenAI
#             self.client = OpenAI(api_key=self.api_key)
#             logger.info("OpenAI LLM service initialized successfully")
#         except ImportError:
#             raise ConfigurationError("OpenAI package not installed. Run: pip install openai")
#         except Exception as e:
#             raise LLMServiceError(f"Failed to initialize OpenAI client: {str(e)}")

#     def generate_sql(self, natural_language_query: str, table_info: str) -> str:
#         logger.info("Note: LLM service is now handled by LangChain SQL Agent in TextToSQLService")
#         return "This method is deprecated - use LangChain SQL Agent instead"


class GeminiLLMService(LLMService):

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ConfigurationError("Gemini API key not configured")

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            self.client = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=settings.GEMINI_TEMPERATURE,
                google_api_key=self.api_key,
            )
            logger.info("Gemini LLM service initialized successfully")
        except ImportError:
            raise ConfigurationError("Gemini package not installed. Run: pip install langchain-google-genai")
        except Exception as e:
            raise LLMServiceError(f"Failed to initialize Gemini client: {str(e)}")

    def generate_sql(self, natural_language_query: str, table_info: str) -> str:
        try:
            prompt = (
                f"### Table Information:\n{table_info}\n\n" f"### Question:\n{natural_language_query}\n\n### SQL Query:"
            )
            return self.client.invoke(prompt)
        except Exception as e:
            raise LLMServiceError(f"Gemini generation failed: {str(e)}")


def create_llm_service(service_type: str = "gemini") -> LLMService:
    service_type = service_type.lower()

    # if service_type == "openai":
    #     return OpenAILLMService()
    if service_type == "gemini":
        return GeminiLLMService()
    else:
        raise ConfigurationError(f"Unsupported LLM service type: {service_type}")
