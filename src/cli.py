"""
CLI module: provides the text-based user interface for the messaging app.

Handles prompt display, message printing, and system command parsing
(e.g. switching channels).
"""
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

def header(channel: str) -> str:
    """Return the bold ``[rfcrypt][channel]`` header."""
    return f"[rfcrypt][{channel}]"

def print_msg(channel: str, msg: str) -> None:
    """Print a received message with a bold header."""
    print_formatted_text(
        HTML(f"<b>{header(channel)}</b> RECEIVED MESSAGE -> {msg}")
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

    if cmd.startswith("channel="):
        field = "channel"
        value_tmp = cmd[len("channel="):]

        if value_tmp.startswith("ch") and value_tmp[2:].isdigit():
            value = value_tmp

    return field, value