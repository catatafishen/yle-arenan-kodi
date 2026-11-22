"""Errors raised by the Yle service layer."""


class YleError(Exception):
    """Base class for expected service failures."""


class YleRequestError(YleError):
    """A network or HTTP request failed."""


class YleResponseError(YleError):
    """A response was malformed or missing required data."""


class YleUnavailableError(YleError):
    """The requested content is not currently playable."""


class YleConfigurationError(YleError):
    """The add-on is missing required configuration."""
