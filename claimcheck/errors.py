"""Error types that map onto the CLI exit codes."""


class ConfigError(Exception):
    """Invalid claims file or CLI arguments. Exit code 2."""

    def __init__(self, messages):
        if isinstance(messages, str):
            messages = [messages]
        self.messages = [str(item) for item in messages if str(item)]
        super().__init__("\n".join(self.messages))


class ClaimFailed(Exception):
    """The claim was evaluated and is false. Result FAIL."""


class CheckError(Exception):
    """The claim could not be evaluated. Result ERROR. Other claims still run."""
