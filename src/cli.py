"""
CLI module: provides the text-based user interface for the messaging app.

Handles prompt display, message printing, and system command parsing
(e.g. switching channels).
"""


def get_msg(channel: str, cipher: str) -> str:
    """Display a bold prompt and return the user's typed message."""
    return input(
        '\033[1m' + '[rfcrypt]'
        + f'[{channel}]'
        + f'[{cipher}]'
        + '\033[0m'
        + ' YOU-> '
    )


def print_msg(channel: str, cipher: str, msg: str) -> None:
    """Print a received message with a bold header."""
    print(
        '\033[1m' + '[rfcrypt]'
        + f'[{channel}]'
        + f'[{cipher}]'
        + '\033[0m'
        + f' RECEIVED MESSAGE -> {msg}'
    )


def parse_cmd(cmd: str) -> tuple[str, str]:
    """
    Parse a system command of the form ``field=value``.

    Currently supported commands:
        channel=chN   — switch to channel N

    Returns:
        (field, value) on success, or ("", "") if the command is
        unrecognised or malformed.
    """
    field = ""
    value = ""

    # TODO - add system command for encryption type

    if cmd.startswith("channel="):
        field = "channel"
        # Extract the value after the '=' (no off-by-one trim)
        value_tmp = cmd[len("channel="):]

        # Validate: must look like "ch<digits>"
        if value_tmp.startswith("ch") and value_tmp[2:].isdigit():
            value = value_tmp

    return field, value