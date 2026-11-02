class UserFacingError(Exception):
    """An error whose message is safe to show to the user.

    Anything else that goes wrong while processing a file is replaced by a generic
    message before it is stored, because exception text can carry server details
    such as hosts and paths. The full error is always logged.
    """
