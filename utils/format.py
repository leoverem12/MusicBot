def format_bytes(bytes_value):
    if bytes_value is None:
        return "0B"
    if bytes_value < 1024:
        return f"{bytes_value:.2f}B"
    elif bytes_value < 1024**2:
        return f"{bytes_value/1024:.2f}KB"
    elif bytes_value < 1024**3:
        return f"{bytes_value/(1024**2):.2f}MB"
    else:
        return f"{bytes_value/(1024**3):.2f}GB"


def format_time(seconds):
    if seconds is None:
        return "Unknown"
    minutes = int(seconds) // 60
    seconds = int(seconds) % 60
    return f"{minutes}:{seconds:02}"