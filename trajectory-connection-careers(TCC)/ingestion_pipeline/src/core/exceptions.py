class IngestionError(Exception):
    """Base class for ingestion exceptions."""
    pass

class CollectionError(IngestionError):
    """Raised when data collection fails."""
    pass

class DiscoveryError(IngestionError):
    """Raised when entity discovery fails."""
    pass

class ConfigurationError(IngestionError):
    """Raised when collector configuration is invalid."""
    pass

class LLMError(Exception):
    """Base class for LLM-related errors."""
    pass

class LLMParseError(LLMError):
    """Raised when LLM output cannot be parsed or fails validation."""
    pass

class LLMRateLimitError(LLMError):
    """Raised when LLM API rate limits are exceeded."""
    pass

class AgentExecutionError(Exception):
    """Raised when an agent node fails to execute correctly."""
    pass
