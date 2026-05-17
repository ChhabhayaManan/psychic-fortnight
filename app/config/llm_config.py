"""LLM provider configuration."""

from typing import Optional

from langchain_core.language_models import BaseLLM

from .settings import get_settings


class LLMConfig:
    """
    LLM configuration and provider management.

    Handles initialization and configuration of LLM providers,
    currently supporting IBM watsonx.ai.
    """

    def __init__(self):
        """Initialize LLM configuration."""
        self.settings = get_settings()
        self._llm: Optional[BaseLLM] = None

    def get_llm(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> BaseLLM:
        """
        Get configured LLM instance.

        Args:
            temperature: Override default temperature
            max_tokens: Override default max tokens
            **kwargs: Additional LLM parameters

        Returns:
            Configured LLM instance
        """
        self.require_llm_ready()
        if self._llm is None:
            if self.settings.llm_provider == 'Gemini':
                self._llm = self._create_gemini_llm(temperature=temperature, max_tokens=max_tokens, **kwargs)
            elif self.settings.llm_provider == 'Groq':
                self._llm = self._create_groq_llm(temperature=temperature, max_tokens=max_tokens, **kwargs)
            else:
                self._llm = self._create_watsonx_llm(temperature=temperature, max_tokens=max_tokens, **kwargs)
        return self._llm

    def validate_llm_ready(self) -> bool:
        """Return whether credentials are configured."""
        if self.settings.llm_provider == "Gemini":
            return bool(self.settings.gemini_api_key)
        elif self.settings.llm_provider == "Groq":
            return bool(self.settings.groq_api_key)
        return bool(self.settings.watsonx_api_key and self.settings.watsonx_project_id)

    def require_llm_ready(self) -> None:
        """Raise a clear error when LLM credentials are missing."""
        if not self.validate_llm_ready():
            raise RuntimeError(
                f"{self.settings.llm_provider} credentials are not configured. Set the appropriate API keys."
            )

    def _create_watsonx_llm(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> BaseLLM:
        from langchain_ibm import WatsonxLLM  # lazy import
        """
        Create IBM watsonx.ai LLM instance.

        Args:
            temperature: Model temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model parameters

        Returns:
            Configured WatsonxLLM instance
        """
        params = {
            "decoding_method": "greedy",
            "temperature": temperature or self.settings.llm_temperature,
            "max_new_tokens": max_tokens or self.settings.llm_max_tokens,
            "min_new_tokens": 1,
            "repetition_penalty": 1.0,
        }
        params.update(kwargs)

        return WatsonxLLM(
            model_id=self.settings.llm_model,
            url=self.settings.watsonx_url,
            apikey=self.settings.watsonx_api_key,
            project_id=self.settings.watsonx_project_id,
            params=params
        )

    def _create_gemini_llm(self, temperature=None, max_tokens=None, **kwargs) -> BaseLLM:
        from langchain_google_genai import ChatGoogleGenerativeAI  # lazy import
        return ChatGoogleGenerativeAI(
            model=self.settings.gemini_model,
            google_api_key=self.settings.gemini_api_key,
            temperature=temperature or self.settings.llm_temperature,
            max_output_tokens=max_tokens or self.settings.llm_max_tokens,
            **kwargs
        )

    def _create_groq_llm(self, temperature=None, max_tokens=None, **kwargs) -> BaseLLM:
        from langchain_groq import ChatGroq  # lazy import
        return ChatGroq(
            model_name=self.settings.groq_model,
            groq_api_key=self.settings.groq_api_key,
            temperature=temperature or self.settings.llm_temperature,
            max_tokens=max_tokens or self.settings.llm_max_tokens,
            **kwargs
        )

    def get_extraction_llm(self) -> BaseLLM:
        """
        Get LLM configured for extraction tasks.

        Uses lower temperature for more deterministic outputs.
        """
        return self.get_llm(temperature=0.1)

    def get_reasoning_llm(self) -> BaseLLM:
        """
        Get LLM configured for reasoning tasks.

        Uses slightly higher temperature for more creative reasoning.
        """
        return self.get_llm(temperature=0.3)

    def get_summarization_llm(self) -> BaseLLM:
        """
        Get LLM configured for summarization tasks.

        Uses moderate temperature for balanced summaries.
        """
        return self.get_llm(temperature=0.2)

    def reset(self) -> None:
        """Reset LLM instance (useful for testing)."""
        self._llm = None


# Global LLM config instance
_llm_config: Optional[LLMConfig] = None


def get_llm_config() -> LLMConfig:
    """
    Get global LLM config instance.

    Returns:
        Global LLMConfig instance
    """
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig()
    return _llm_config


def get_llm(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs
) -> BaseLLM:
    """
    Convenience function to get configured LLM.

    Args:
        temperature: Override default temperature
        max_tokens: Override default max tokens
        **kwargs: Additional LLM parameters

    Returns:
        Configured LLM instance
    """
    return get_llm_config().get_llm(
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )

# Made with Bob
