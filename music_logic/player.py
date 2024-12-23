import discord
import asyncio
import time
import traceback
from collections import deque
import re
import os
from config import YTDL_OPTS, FFMPEG_OPTS, IDLE_TIMEOUT
from music_logic import download as download_utils
from utils import format as format_utils
import yt_dlp as youtube_dl
from utils.embed import create_embed

# Ці змінні потім замінюються з main.py. Можна зробити клас з методами.
music_queues = {}
players = {}
last_activity = {}
bot = None
current_volume = 100.0
session_messages = {}
playlists = {}
looping = {}

def contains_russian_letters(text):
    if not text:
        return False
    return bool(re.search(r'[ыъэ]', text, re.IGNORECASE))

async def search_youtube_tracks(search_term, max_results=5):
    ydl_opts_search = YTDL_OPTS.copy()
    ydl_opts_search['extract_flat'] = True
    ydl_opts_search['quiet'] = True
    ydl_opts_search['no_warnings'] = True
    ydl_opts_search['default_search'] = 'ytsearch'
    
    with youtube_dl.YoutubeDL(ydl_opts_search) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{max_results}:{search_term}", download=False)
            if info and 'entries' in info:
                return info['entries']
            else:
                return []
        except Exception as e:
            print(f"Error during search: {e}")
            traceback.print_exc()
            return []

async def play(interaction: discord.Interaction, search_term: str):
    await interaction.response.defer()
    if not interaction.user.voice:
        embed = create_embed("Ви повинні бути у голосовому каналі, щоб використовувати цю команду.")
        await interaction.followup.send(embed=embed)
        return
    voice_channel = interaction.user.voice.channel
    if not voice_channel:
        embed = create_embed("Ви повинні бути у голосовому каналі, щоб використовувати цю команду.")
        await interaction.followup.send(embed=embed)
        return

    guild_id = interaction.guild_id
    if guild_id not in music_queues:
        music_queues[guild_id] = deque()
    
    voice_client = interaction.guild.voice_client
    
    if voice_client:
        if voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    else:
        await voice_channel.connect()

    if 'playlist' in search_term or 'list=' in search_term:
      await queue_playlist(interaction, search_term)
    else:
      tracks = await search_youtube_tracks(search_term)
      if not tracks:
          embed = create_embed("Не знайдено треків за вашим запитом.")
          await interaction.followup.send(embed=embed)
          return
      
      embed = create_embed("Оберіть трек, натиснувши на відповідну кнопку:")
      
      for i, track in enumerate(tracks):
          embed.add_field(
              name=f"{i+1}. {track.get('title', 'Unknown Title')}",
              value=f"({format_utils.format_time(track.get('duration', 0))})",
              inline=False
          )
      
      buttons = [discord.ui.Button(label=str(i+1), style=discord.ButtonStyle.primary, custom_id=str(i+1)) for i in range(len(tracks))]
      buttons.append(discord.ui.Button(label="Відміна", style=discord.ButtonStyle.danger, custom_id="cancel"))
      view = discord.ui.View()
      for button in buttons:
          view.add_item(button)
      
      message = await interaction.followup.send(embed=embed, view=view)
      if guild_id not in session_messages:
          session_messages[guild_id] = []
      session_messages[guild_id].append(message.id)
      
      def check(interaction_button):
          return interaction_button.user == interaction.user and interaction_button.message.id == message.id
      
      try:
          interaction_button = await bot.wait_for("interaction", check=check, timeout=30)
          if interaction_button:
            if interaction_button.data['custom_id'] == "cancel":
                await message.delete()
                embed = create_embed("Вибір скасовано.")
                await interaction.followup.send(embed=embed)
                session_messages[guild_id].remove(message.id)
                return
            else:
                selected_track_index = int(interaction_button.data['custom_id']) - 1
                selected_track = tracks[selected_track_index]
                if contains_russian_letters(selected_track.get('title', '')):
                    embed = create_embed("Цей трек містить російські літери і не може бути відтворений.")
                    await interaction.followup.send(embed=embed)
                    return
                await message.delete()
                session_messages[guild_id].remove(message.id)
                await play_music(interaction, selected_track['url'])
          else:
              await message.delete()
              embed = create_embed("Час вибору треку вийшов.")
              await interaction.followup.send(embed=embed)
              session_messages[guild_id].remove(message.id)
              return
      except asyncio.TimeoutError:
          await message.delete()
          embed = create_embed("Час вибору треку вийшов.")
          await interaction.followup.send(embed=embed)
          session_messages[guild_id].remove(message.id)
          return
      except Exception as e:
          print(f"Error during track selection: {e}")
          traceback.print_exc()
          embed = create_embed("Виникла помилка під час вибору треку.")
          await interaction.followup.send(embed=embed)
          return
    
    last_activity[guild_id] = time.time()

async def queue_playlist(interaction: discord.Interaction, playlist_url):
    guild_id = interaction.guild_id
    embed = create_embed("Додаю пісні з плейліста...")
    message = await interaction.followup.send(embed=embed)
    if guild_id not in session_messages:
        session_messages[guild_id] = []
    session_messages[guild_id].append(message.id)
    
    try:
      with youtube_dl.YoutubeDL(YTDL_OPTS) as ydl:
          info = None
          try:
              info = ydl.extract_info(playlist_url, download=False)
          except youtube_dl.utils.DownloadError as e:
             print(f"Помилка при завантаженні плейліста: {e}")
             traceback.print_exc()
             embed = create_embed("Помилка при завантаженні плейліста.", str(e))
             await update_message(message, embed=embed)
             return
          except Exception as e:
              print(f"Виникла помилка при завантаженні плейліста: {e}")
              traceback.print_exc()
              embed = create_embed("Виникла помилка при завантаженні плейліста.", str(e))
              await update_message(message, embed=embed)
              return

          if info and 'entries' in info:
             playlist_entries = []
             for entry in info['entries']:
                if entry and 'url' in entry and not entry.get('is_live', False) and not entry.get('private', False):
                    try:
                      if contains_russian_letters(entry.get('title', '')):
                        print(f"Пропущено відео з російськими літерами: {entry.get('title', 'Unknown Title')}")
                        continue
                      music_queues[guild_id].append(entry['url'])
                      playlist_entries.append(entry)
                    except Exception as e:
                       print(f"Помилка при додаванні пісні до черги: {e}")
                       traceback.print_exc()
                       embed = create_embed("Помилка при додаванні пісні до черги.", str(e))
                       await update_message(message, embed=embed)
                       continue
             if playlist_entries:
                if guild_id not in playlists:
                    playlists[guild_id] = {}
                playlists[guild_id][playlist_url] = playlist_entries
                embed = create_embed("Пісні з плейліста додано до черги.")
                await update_message(message, embed=embed)
             else:
                embed = create_embed("Не знайдено пісень у плейлісті або всі пісні приватні/з російськими літерами.")
                await update_message(message, embed=embed)
             voice_client = interaction.guild.voice_client
             if not voice_client or not voice_client.is_playing():
                if music_queues[guild_id]:
                    await play_music(interaction, music_queues[guild_id][0])
                    music_queues[guild_id].popleft()

          else:
              embed = create_embed("Не знайдено пісень у плейлісті.")
              await update_message(message, embed=embed)
    except Exception as e:
         embed = create_embed("Виникла помилка при завантаженні плейліста.", str(e))
         await update_message(message, embed=embed)
         print(f"Виникла помилка при завантаженні плейліста: {e}")
         traceback.print_exc()
        
async def play_music(interaction: discord.Interaction, search_term):
    global current_volume
    voice_client = interaction.guild.voice_client
    
    max_retries = 3
    retries = 0
    
    while retries < max_retries:
        try:
            with youtube_dl.YoutubeDL(YTDL_OPTS) as ydl:
                embed = create_embed(f'Пошук {search_term}')
                message = await interaction.followup.send(embed=embed)
                if interaction.guild_id not in session_messages:
                    session_messages[interaction.guild_id] = []
                session_messages[interaction.guild_id].append(message.id)

                search_term_with_music = f"{search_term} music"
                info = None
                try:
                    info = await download_utils.extract_info_with_retry(ydl, search_term_with_music, retries, max_retries, message, interaction)
                    if info is None:
                       embed = create_embed(f"Не вдалося отримати інформацію про пісню: {search_term}. Пропускаю.")
                       await update_message(message, embed=embed)
                       break
                except Exception as e:
                    retries += 1
                    print(f"Виникла помилка: {e}. Повторна спроба...({retries}/{max_retries})")
                    traceback.print_exc()
                    await asyncio.sleep(2)
                    embed = create_embed(f"Виникла помилка: {e}. Повторна спроба...({retries}/{max_retries})")
                    await update_message(message, embed=embed)
                    continue
                
                if info and 'entries' in info:
                    filtered_entries = [
                         entry for entry in info['entries']
                            if entry.get('title') and
                            (re.search(r'\b(music|official|audio|lyric(s)?)\b', entry['title'], re.IGNORECASE)
                         or
                            entry.get('categories') and any(re.search(r'\b(music)\b', category, re.IGNORECASE) for category in entry.get('categories'))
                            )
                    ]

                    if filtered_entries:
                      info = filtered_entries[0]
                    else:
                        info = info['entries'][0]
                if info:
                    url = info.get('url')
                    if not url:
                         embed = create_embed(f"Не вдалося отримати інформацію про пісню: {search_term}. Пропускаю.")
                         await update_message(message, embed=embed)
                         break
                    title = info.get('title', 'Unknown Title')
                    if contains_russian_letters(title):
                        embed = create_embed("Цей трек містить російські літери і не може бути відтворений.")
                        await update_message(message, embed=embed)
                        break
                    embed = create_embed(f"Завантаження {title}")
                    await update_message(message, embed=embed)
                    
                    file_path = None
                    try:
                       file_path = await download_utils.download_audio(ydl, url, message, title, retries, max_retries, interaction, info, bot)
                    except Exception as e:
                       print(f"Error downloading song. {e}")
                       traceback.print_exc()
                       embed = create_embed(f"Помилка завантаження {title}: {e}")
                       await update_message(message, embed=embed)
                       continue
                    if file_path:
                      if voice_client:
                        try:
                          if voice_client.is_playing():
                            voice_client.stop()
                          audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(file_path, **FFMPEG_OPTS), volume=current_volume/100.0)
                          voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_handler(interaction), bot.loop))
                          embed = create_embed(f'Зараз грає: {title} 0/{format_utils.format_time(info.get("duration"))}')
                          await update_message(message, embed=embed)
                          players[interaction.guild_id] = (voice_client, title, message, time.time(), info.get("duration"), file_path)
                          asyncio.create_task(track_audio_progress(interaction, message, title))
                          break
                        except Exception as e:
                            retries +=1
                            print(f"ffmpeg error {e}. Retrying... ({retries}/{max_retries})")
                            traceback.print_exc()
                            await asyncio.sleep(2)
                            embed = create_embed(f"ffmpeg error {e}. Retrying... ({retries}/{max_retries})")
                            await update_message(message, embed=embed)

                      else:
                         await interaction.followup.send("Бот не в голосовому каналі. Використайте musi/join спочатку")
                    else:
                      continue
                else:
                   embed = create_embed(f"Не вдалося отримати інформацію про пісню: {search_term}. Пропускаю.")
                   await update_message(message, embed=embed)
                   break
        except Exception as e:
            retries += 1
            print(f"Виникла помилка: {e}. Повторна спроба...({retries}/{max_retries})")
            traceback.print_exc()
            await asyncio.sleep(2)
            embed = create_embed(f"Виникла помилка: {e}. Повторна спроба...({retries}/{max_retries})")
            await update_message(message, embed=embed)
    if retries == max_retries:
      print("Досягнуто максимальної кількості спроб. Неможливо відтворити аудіо.")
      embed = create_embed("Досягнуто максимальної кількості спроб. Неможливо відтворити аудіо.")
      await interaction.followup.send(embed=embed)

async def track_audio_progress(interaction: discord.Interaction, message, title):
    global players
    try:
        guild_id = interaction.guild_id
        voice_client = players.get(guild_id, (None,))[0]

        if not voice_client:
            return

        _, _, _, start_time, duration, _ = players.get(guild_id, (None, None, None, None, None, None))
        
        while voice_client and voice_client.is_playing() and guild_id in players:
            try:
                current_time = time.time() - start_time
                if current_time > 0:
                    embed = create_embed(f'Зараз грає: {title} {format_utils.format_time(current_time)}/{format_utils.format_time(duration)}')
                    await update_message(message, embed=embed)
            except Exception:
                pass
            await asyncio.sleep(0.9)
    except Exception as e:
        print(f"Error in track_audio_progress: {e}")
        traceback.print_exc()
    
async def play_next_handler(interaction: discord.Interaction):
    await play_next(interaction)
    
async def play_next(interaction: discord.Interaction):
    global players
    guild_id = interaction.guild_id
    voice_client = interaction.guild.voice_client
    
    try:
        if guild_id in players:
            file_path = players[guild_id][5]
            if file_path and os.path.exists(file_path):
                await asyncio.sleep(0.5)
                try:
                    if voice_client.is_playing():
                        voice_client.stop()
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error in play_next at file remove: {e}")
                    traceback.print_exc()
            players.pop(guild_id, None)
    except Exception as e:
        print(f"Error deleting player in play_next: {e}")
        traceback.print_exc()
    
    if guild_id in looping and looping[guild_id] == True:
      if guild_id in players:
        current_track_url = players[guild_id][5]
        await play_music(interaction, current_track_url)
    elif guild_id in music_queues and music_queues[guild_id]:
        next_song = music_queues[guild_id].popleft()
        await play_music(interaction, next_song)
    else:
        print("Черга порожня, відтворення закінчено. Запускаю відлік неактивності.")
        await start_idle_timeout(interaction)


async def start_idle_timeout(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    last_activity[guild_id] = time.time()
    voice_client = interaction.guild.voice_client

    while guild_id in last_activity:
        
        if not voice_client or not voice_client.is_connected() or not voice_client.channel:
             try:
                 players.pop(guild_id, None)
                 music_queues.pop(guild_id, None)
                 last_activity.pop(guild_id, None)
                 if guild_id in looping:
                    looping.pop(guild_id, None)
             except Exception:
                pass
             print(f"Відключено від голосового каналу на сервері {interaction.guild.name}, через неактивність.")
             return

        if (time.time() - last_activity[guild_id]) > IDLE_TIMEOUT:
           if voice_client and voice_client.is_connected() and voice_client.channel:
                 members = voice_client.channel.members
                 members = [member for member in members if not member.bot]
                 if members:
                    await asyncio.sleep(10)
                    continue
                 else:
                    try:
                        voice_client.stop()
                        await voice_client.disconnect(force=True)
                    except Exception as e:
                        print(f"Error during disconnect on time out {e}")
                        traceback.print_exc()

                    embed = create_embed("Ніхто не використовує бота. Залишаю канал.")
                    await interaction.followup.send(embed=embed)
                    try:
                        players.pop(guild_id, None)
                        music_queues.pop(guild_id, None)
                        last_activity.pop(guild_id, None)
                        if guild_id in looping:
                            looping.pop(guild_id, None)
                    except Exception as e:
                         print(f"Error during disconnect on time out {e}")
                         traceback.print_exc()
                    print(f"Відключено від голосового каналу на сервері {interaction.guild.name}, через неактивність.")
                    return
           else:
                 try:
                      players.pop(guild_id, None)
                      music_queues.pop(guild_id, None)
                      last_activity.pop(guild_id, None)
                      if guild_id in looping:
                            looping.pop(guild_id, None)
                 except:
                     pass
                 return
        await asyncio.sleep(10)


async def skip(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = interaction.guild_id
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
         if guild_id in players:
             title = players[guild_id][1]
             file_path = players[guild_id][5]
             players.pop(guild_id, None)
             if file_path and os.path.exists(file_path):
                 try:
                     os.remove(file_path)
                 except Exception as e:
                     print(f"Error in skip at file remove: {e}")
                     traceback.print_exc()
             voice_client.stop()
             embed = create_embed(f"Пропущено: {title}")
             await interaction.followup.send(embed=embed)
             last_activity[guild_id] = time.time()
         else:
            embed = create_embed("Зараз нічого не грає")
            await interaction.followup.send(embed=embed)
    else:
         embed = create_embed("Нічого пропускати.")
         await interaction.followup.send(embed=embed)
        
async def pause(interaction: discord.Interaction):
    await interaction.response.defer()
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        embed = create_embed("Відтворення призупинено.")
        await interaction.followup.send(embed=embed)
    else:
         embed = create_embed("Нема чого призупиняти.")
         await interaction.followup.send(embed=embed)
    
    if interaction.guild_id in last_activity:
         last_activity[interaction.guild_id] = time.time()

async def resume(interaction: discord.Interaction):
    await interaction.response.defer()
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        embed = create_embed("Відтворення відновлено.")
        await interaction.followup.send(embed=embed)
    else:
       embed = create_embed("Нема чого відновлювати.")
       await interaction.followup.send(embed=embed)

    if interaction.guild_id in last_activity:
        last_activity[interaction.guild_id] = time.time()
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = interaction.guild_id
    voice_client = interaction.guild.voice_client
    if voice_client:
        try:
            await voice_client.disconnect(force=True)
        except asyncio.TimeoutError:
             print("Відключення зайняло занадто багато часу, примусове відключення.")
        except Exception as e:
            print(f"Виникла помилка під час відключення: {e}")
        finally:
            if guild_id in players:
               file_path = players[guild_id][5]
               if file_path and os.path.exists(file_path):
                    try:
                       os.remove(file_path)
                    except Exception as e:
                          print(f"Error in stop at file remove: {e}")
                          traceback.print_exc()
            players.pop(guild_id, None)
            music_queues.pop(guild_id, None)
            last_activity.pop(guild_id, None)
            if guild_id in looping:
                looping.pop(guild_id, None)
            
            if guild_id in session_messages:
                for message_id in session_messages[guild_id]:
                    try:
                        message = await interaction.channel.fetch_message(message_id)
                        await message.delete()
                    except discord.NotFound:
                        pass
                    except Exception as e:
                        print(f"Error deleting message {message_id}: {e}")
                        traceback.print_exc()
                session_messages[guild_id].clear()
            embed = create_embed("Зупинено відтворення та вихід з голосового каналу.")
            await interaction.followup.send(embed=embed)
    else:
        embed = create_embed("Бот не в голосовому каналі.")
        await interaction.followup.send(embed=embed)
    if interaction.guild_id in last_activity:
        last_activity[interaction.guild_id] = time.time()

async def join(interaction: discord.Interaction):
   await interaction.response.defer()
   voice_channel = interaction.user.voice.channel

   if not voice_channel:
       embed = create_embed("Ви повинні бути у голосовому каналі, щоб використовувати цю команду.")
       await interaction.followup.send(embed=embed)
       return
    
   voice_client = interaction.guild.voice_client

   if voice_client:
       if voice_client.channel != voice_channel:
           await voice_client.move_to(voice_channel)
   else:
        await voice_channel.connect()
   embed = create_embed(f"Приєднався до {voice_channel.name}")
   await interaction.followup.send(embed=embed)
   if interaction.guild_id not in last_activity:
        last_activity[interaction.guild_id] = time.time()


async def shutdown(interaction: discord.Interaction):
   await interaction.response.defer()
   confirmation_message = await interaction.followup.send("Ви впевнені, що хочете завершити роботу?")
   await confirmation_message.add_reaction("✅")
   await confirmation_message.add_reaction("❌")
    
   def check(reaction, user):
         return user == interaction.user and str(reaction.emoji) in ["✅", "❌"]
    
   try:
      reaction, user = await bot.wait_for("reaction_add", timeout=10.0, check=check)
    
      if str(reaction.emoji) == "✅":
          embed = create_embed("Завершаю роботу [Видалення кешу]")
          await update_message(confirmation_message, embed=embed)

          for guild_id, player_data in players.items():
              if player_data:
                  file_path = player_data[5]
                  if file_path and os.path.exists(file_path):
                       try:
                           os.remove(file_path)
                       except Exception as e:
                             print(f"Error in shutdown at file remove: {e}")
                             traceback.print_exc()

          embed = create_embed("Завершаю роботу [Завершення]")
          await update_message(confirmation_message, embed=embed)
          await bot.close()
      else:
          embed = create_embed("Завершення відмінено")
          await update_message(confirmation_message, embed=embed)

   except asyncio.TimeoutError:
        embed = create_embed("Завершення скасовано через тайм-аут.")
        await update_message(confirmation_message, embed=embed)
   except Exception as e:
        print(f"Error during shutdown: {e}")
        traceback.print_exc()
        embed = create_embed(f"Виникла помилка під час завершення: {e}")
        await update_message(confirmation_message, embed=embed)

async def update_message(message, content=None, embed=None, view=None):
    if isinstance(message, discord.WebhookMessage):
        await message.edit(content=content, embed=embed, view=view)
    else:
        await message.edit(content=content, embed=embed, view=view)

async def playlist(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = interaction.guild_id
    if guild_id not in playlists or not playlists[guild_id]:
        embed = create_embed("Немає завантажених плейлистів.")
        await interaction.followup.send(embed=embed)
        return
    
    playlist_urls = list(playlists[guild_id].keys())
    if not playlist_urls:
        embed = create_embed("Немає завантажених плейлистів.")
        await interaction.followup.send(embed=embed)
        return
    
    current_page = 0
    items_per_page = 5
    
    async def update_playlist_message(page, message=None):
        start_index = page * items_per_page
        end_index = start_index + items_per_page
        
        playlist_url = playlist_urls[0]
        playlist_entries = playlists[guild_id][playlist_url]
        
        current_entries = playlist_entries[start_index:end_index]
        
        embed = create_embed(f"Треки з плейлиста:", f"Сторінка {page + 1}/{len(playlist_entries) // items_per_page + 1}")
        
        for i, entry in enumerate(current_entries):
            embed.add_field(
                name=f"{start_index + i + 1}. {entry.get('title', 'Unknown Title')}",
                value=f"({format_utils.format_time(entry.get('duration', 0))})",
                inline=False
            )
        
        buttons = []
        if page > 0:
            buttons.append(discord.ui.Button(label="Назад", style=discord.ButtonStyle.primary, custom_id="prev"))
        if end_index < len(playlist_entries):
            buttons.append(discord.ui.Button(label="Вперед", style=discord.ButtonStyle.primary, custom_id="next"))
        for i, entry in enumerate(current_entries):
            buttons.append(discord.ui.Button(label=str(start_index + i + 1), style=discord.ButtonStyle.success, custom_id=str(start_index + i + 1)))
        buttons.append(discord.ui.Button(label="Відміна", style=discord.ButtonStyle.danger, custom_id="cancel"))
        view = discord.ui.View()
        for button in buttons:
            view.add_item(button)
        
        if message:
            await update_message(message, embed=embed, view=view)
        else:
            message = await interaction.followup.send(embed=embed, view=view)
            if guild_id not in session_messages:
                session_messages[guild_id] = []
            session_messages[guild_id].append(message.id)
        
        return message
    
    message = await update_playlist_message(current_page)
    
    def check(interaction_button):
        return interaction_button.user == interaction.user and interaction_button.message.id == message.id
    
    while True:
        try:
            interaction_button = await bot.wait_for("interaction", check=check, timeout=30)
            if interaction_button.data['custom_id'] == "prev":
                current_page -= 1 
                message = await update_playlist_message(current_page, message)
            elif interaction_button.data['custom_id'] == "next":
                current_page += 1
                message = await update_playlist_message(current_page, message)
            elif interaction_button.data['custom_id'] == "cancel":
                await message.delete()
                embed = create_embed("Вибір скасовано.")
                await interaction.followup.send(embed=embed)
                session_messages[guild_id].remove(message.id)
                return
            else:
                selected_track_index = int(interaction_button.data['custom_id']) - 1
                playlist_url = playlist_urls[0]
                selected_track = playlists[guild_id][playlist_url][selected_track_index]
                await message.delete()
                session_messages[guild_id].remove(message.id)
                await play_music(interaction, selected_track['url'])
                return
        except asyncio.TimeoutError:
            await message.delete()
            embed = create_embed("Час вибору треку вийшов.")
            await interaction.followup.send(embed=embed)
            session_messages[guild_id].remove(message.id)
            return
        except Exception as e:
            print(f"Error during playlist selection: {e}")
            traceback.print_exc()
            embed = create_embed("Виникла помилка під час вибору треку.")
            await interaction.followup.send(embed=embed)
            return
        
async def loop(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = interaction.guild_id
    if guild_id not in looping:
        looping[guild_id] = False
    looping[guild_id] = not looping[guild_id]
    if looping[guild_id]:
        embed = create_embed("Зациклення треку увімкнено.")
    else:
        embed = create_embed("Зациклення треку вимкнено.")
    await interaction.followup.send(embed=embed)