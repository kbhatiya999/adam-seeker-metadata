"""Exceptions shared by all Seeker SDKs."""


class SeekerError(Exception):
    """Base class for every error raised on purpose by the Seeker SDKs."""


class ConfigError(SeekerError):
    """Invalid or missing configuration (for example a method that needs an API key)."""


class SourceError(SeekerError):
    """A video source could not produce what was asked of it."""


class TranscriptError(SeekerError):
    """A transcript method could not produce a transcript."""


class PluginError(SeekerError):
    """A plugin was not found or could not be loaded."""
