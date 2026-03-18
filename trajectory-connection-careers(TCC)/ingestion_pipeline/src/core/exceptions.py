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
