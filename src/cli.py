# Argument parsing and dispatch for: record, encrypt, modulate, demodulate, decrypt, play

def get_msg(channel: str, cipher: str) -> str:
    return input('\033[1m' + '[rfcrypt]' + f'[{channel}]' + f'[{cipher}]' + '\033[0m' + ' YOU-> ')
        
    
def print_msg(channel: str, cipher: str, msg: str) -> str:
    print('\033[1m' + '[rfcrypt]' + f'[{channel}]' + f'[{cipher}]' + '\033[0m' + f' RECEIVED MESSAGE -> {msg}')

def parse_cmd(cmd: str) -> tuple[str, str]:
    field = ""
    value = ""

    # TODO - add system command for encryption type

    """
    System commands must be in the form field=value
    """
    if cmd.startswith("channel="):
        field = "channel"
        value_tmp = cmd[len("channel="):len(cmd) - 1]

        if value_tmp.startswith("ch") and value_tmp[2:len(value_tmp) - 1].isdigit():
            value = value_tmp
    
    return field, value