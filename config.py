COMMAND_PREFIX = 'musi/'
IDLE_TIMEOUT = 180

YTDL_OPTS = {
    'format': 'bestaudio[ext=m4a]/bestaudio/best',
    'outtmpl': {'default': '%(title)s.%(ext)s'},
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'verbose': False,
    'fragment_retries': 10,
    'retries': 10,
    'file_access_retries': 5,
    'buffersize': 1024 * 1024,
    'http_chunk_size': 10485760,
    'socket_timeout': 10,
    'extract_flat': 'in_playlist',
    'concurrent_fragment_downloads': 3,
    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
}

FFMPEG_OPTS = {'options': '-vn -bufsize 2M -maxrate 2M'}