class NotFoundError(Exception):
    """No match exists with the given ID."""


class ConflictError(Exception):
    """The requested operation is not valid for the match's current state."""
