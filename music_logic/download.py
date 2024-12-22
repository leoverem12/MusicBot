import yt_dlp as youtube_dl
import asyncio
import time
import os
import threading
import traceback
from utils import format as format_utils
from config import YTDL_OPTS

async def download_audio(ydl, url, message, title, retries, max_retries, ctx, info, bot):
    file_path = None
    delay = 1
    current_retries = 0
    
    def run_download(url, file_path_holder, message, title, retries, max_retries, ctx, info):
      nonlocal file_path
      nonlocal current_retries
      start_time = time.time()
      total_bytes = 0
      downloaded_bytes = 0
      while current_retries < max_retries:
        try:

           info_download = ydl.extract_info(url, download=False)
           
           if not info_download:
               raise ValueError("Could not extract video information")

           if info_download.get('filesize'):
             total_bytes = info_download['filesize']

           asyncio.run_coroutine_threadsafe(update_message(message, f"Завантаження {title}..."), bot.loop)
          
           def progress_hook(d):
                nonlocal downloaded_bytes
                nonlocal start_time

                if d['status'] == 'downloading':
                    downloaded_bytes = d.get('downloaded_bytes', 0)
                    if total_bytes:
                        percentage = min(100, int(downloaded_bytes * 100 / total_bytes))
                    else:
                        percentage = 0

                    time_elapsed = time.time() - start_time
                    if time_elapsed > 0 and downloaded_bytes > 0:
                      speed = downloaded_bytes / time_elapsed

                      speed_formatted = format_utils.format_bytes(speed)
                      downloaded_formatted = format_utils.format_bytes(downloaded_bytes)
                    else:
                      speed_formatted = "0B/s"
                      downloaded_formatted = "0B"

                    if total_bytes:
                       total_formatted = format_utils.format_bytes(total_bytes)

                       progress_str = f"{percentage}%[{'='*int(percentage/5)}{' '*(20-int(percentage/5))}] {downloaded_formatted}/{total_formatted} {speed_formatted} in {format_utils.format_time(time_elapsed)}"
                    else:
                       progress_str = f"{percentage}%[{'='*int(percentage/5)}{' '*(20-int(percentage/5))}] {downloaded_formatted} {speed_formatted} in {format_utils.format_time(time_elapsed)}"

                    asyncio.run_coroutine_threadsafe(update_message(message, f"Завантаження {title}\n{progress_str}"), bot.loop)
           
           ydl_opts = YTDL_OPTS
           ydl_opts['progress_hooks'] = [progress_hook]
            
           download_info = ydl.extract_info(url, download=True)

           if not download_info:
                raise ValueError("Download failed")

           if 'requested_downloads' in download_info:
                file_path = download_info['requested_downloads'][0]['filepath']
           else:
                file_name = ydl.prepare_filename(download_info)
                file_path = file_name.replace('.webm', '.mp3').replace('.m4a', '.mp3')
           
           if file_path and os.path.exists(file_path):
               time_elapsed = time.time() - start_time
               if total_bytes:
                    total_formatted = format_utils.format_bytes(total_bytes)
                    speed = downloaded_bytes/time_elapsed
                    speed_formatted = format_utils.format_bytes(speed)
                    asyncio.run_coroutine_threadsafe(update_message(message, f"Завантажено: {title}\n100%[====================] {total_formatted} {speed_formatted} in {format_utils.format_time(time_elapsed)}"), bot.loop)
               else:
                   asyncio.run_coroutine_threadsafe(update_message(message, f"Завантажено: {title} in {format_utils.format_time(time_elapsed)}"), bot.loop)

               file_path_holder[0] = file_path
               return
           else:
                raise Exception("Download completed but file not found")
            
        except Exception as e:
            current_retries += 1
            error_msg = str(e)
            print(f"Download error (attempt {current_retries}/{max_retries}): {error_msg}")
            traceback.print_exc()
           
            if current_retries < max_retries:
                 time.sleep(delay)
                 delay *= 2
                 asyncio.run_coroutine_threadsafe(update_message(message, f"Помилка завантаження: {error_msg}. Повторна спроба...({current_retries}/{max_retries})"), bot.loop)
            else:
               asyncio.run_coroutine_threadsafe(update_message(message, f"Не вдалося завантажити після {max_retries} спроб: {error_msg}"), bot.loop)

            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
    
    
    file_path_holder = [None]
    download_thread = threading.Thread(target=run_download, args=(url, file_path_holder, message, title, retries, max_retries, ctx, info))
    download_thread.start()
    download_thread.join()
    
    return file_path_holder[0]


async def extract_info_with_retry(ydl, search_term_with_music, retries, max_retries, message, ctx):
    info = None
    delay = 1
    current_retries = 0
    
    while current_retries < max_retries:
        try:
            info = ydl.extract_info(search_term_with_music, download=False)

            if not isinstance(info, dict):
                 raise ValueError(f"Invalid response format from yt-dlp: {type(info)}")

            if info:
                return info
            else:
                return None
           
        except youtube_dl.utils.DownloadError as e:
             current_retries += 1
             print(f"Info extraction error (attempt {current_retries}/{max_retries}): {str(e)}")
             traceback.print_exc()
             
             if current_retries < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
                await update_message(message, f"Info extraction error: {str(e)}. Retrying... ({current_retries}/{max_retries})")
             else:
                await update_message(message, f"Failed to extract info after {max_retries} attempts: {str(e)}")
                return None

        except Exception as e:
            current_retries += 1
            print(f"Unexpected error (attempt {current_retries}/{max_retries}): {str(e)}")
            traceback.print_exc()

            if current_retries < max_retries:
               await asyncio.sleep(delay)
               delay *= 2
               await update_message(message, f"Unexpected error: {str(e)}. Retrying... ({current_retries}/{max_retries})")
            else:
                await update_message(message, f"Failed after {max_retries} attempts: {str(e)}")
                return None

    return None
  
async def update_message(message, content):
    await message.edit(content=content)