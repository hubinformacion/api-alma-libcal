class PilotError(Exception):
    """A safe diagnostic, containing neither credentials nor source records."""


class ConfigError(PilotError):
    pass


class SourceError(PilotError):
    pass


class PublicationError(PilotError):
    pass
