import discord
import asyncio
import traceback
import time
from music_logic import player
from utils import format as format_utils
from config import FFMPEG_OPTS  # Імпортуємо FFMPEG_OPTS з config.py
from utils.embed import create_embed

music_queues = {}
players = {}
last_activity = {}
bot = None
current_volume = 100.0

async def volume(interaction: discord.Interaction, level: str):
    await interaction.response.defer()

    if level.lower() == 'from':
         embed = create_embed("Неправильний формат. Використовуйте /volume <number>")
         await interaction.followup.send(embed=embed)
         return

    try:
         level = int(level)
    except ValueError:
        embed = create_embed("Будь ласка, введіть числове значення гучності.")
        await interaction.followup.send(embed=embed)
        return

    if level < 0 or level > 1000:
        embed = create_embed("Рівень гучності повинен бути від 0 до 1000.")
        await interaction.followup.send(embed=embed)
        return
    await start_volume_vote(interaction, level)
    if interaction.guild_id in last_activity:
        last_activity[interaction.guild_id] = time.time()

async def start_volume_vote(interaction: discord.Interaction, target_volume):
   voice_channel = interaction.user.voice.channel
   if not voice_channel:
        embed = create_embed("Ви повинні бути у голосовому каналі, щоб використовувати цю команду.")
        await interaction.followup.send(embed=embed)
        return

   members = voice_channel.members
   members_count = len(members)
   if members_count <= 1:
        await set_volume(interaction, target_volume, interaction)
        return

   embed = create_embed(f"Починається голосування за встановлення гучності на {target_volume}%.", "**УВАГА: Гучність 1000% може бути шкідливою для слуху!**")
   message = await interaction.followup.send(embed=embed)
   await message.add_reaction("✅")
   await message.add_reaction("❌")

   def check(reaction, user):
        return user != bot.user and str(reaction.emoji) in ["✅", "❌"] and user in members and reaction.message.id == message.id
   
   try:
        reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)

        yes_votes = 0
        no_votes = 0
        for reaction in message.reactions:
             if str(reaction.emoji) == "✅":
                yes_votes = reaction.count -1
             if str(reaction.emoji) == "❌":
                no_votes = reaction.count - 1
        if yes_votes >= no_votes:
             await set_volume(interaction, target_volume, interaction)
             embed = create_embed(f"Голосування за встановлення гучності на {target_volume}% завершено.", f"✅: {yes_votes}, ❌: {no_votes}. Гучність встановлено.")
             await player.update_message(message, embed=embed)
        else:
           embed = create_embed(f"Голосування за встановлення гучності на {target_volume}% завершено.", f"✅: {yes_votes}, ❌: {no_votes}. Гучність не змінено.")
           await player.update_message(message, embed=embed)

   except asyncio.TimeoutError:
        embed = create_embed(f"Голосування за встановлення гучності на {target_volume}% закінчилось через тайм-аут.")
        await player.update_message(message, embed=embed)

   except Exception as e:
         print(f"Error in volume voting: {e}")
         traceback.print_exc()


async def set_volume(interaction: discord.Interaction, target_volume, interaction_for_restart):
   global current_volume
   current_volume = float(target_volume)
   voice_client = interaction.guild.voice_client
    
   if voice_client and voice_client.is_connected():
        if target_volume == 1000:
            current_playing = None
            if interaction_for_restart.guild_id in players:
                 current_playing = players.pop(interaction_for_restart.guild_id)
            try:
                 voice_client.stop()
                 await voice_client.disconnect(force=True)
            except Exception as e:
                print(f"Error disconnecting bot: {e}")
                traceback.print_exc()
            
            voice_channel = interaction_for_restart.user.voice.channel
            if voice_channel:
               try:
                  await voice_channel.connect()
               except Exception as e:
                    print(f"Error connecting to voice channel {e}")
                    traceback.print_exc()
                    embed = create_embed(f"Не вдалося приєднатися до голосового каналу, виникла помилка: {e}")
                    await interaction.followup.send(embed=embed)
                    return
                
               while not voice_client.is_connected():
                     await asyncio.sleep(0.1)

               if current_playing:
                     try:
                          audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(current_playing[5], **FFMPEG_OPTS), volume=current_volume/100.0)
                          voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(player.play_next_handler(interaction_for_restart), bot.loop))
                          players[interaction_for_restart.guild_id] = (interaction_for_restart.guild.voice_client, current_playing[1], current_playing[2], current_playing[3], current_playing[4], current_playing[5])
                          asyncio.create_task(player.track_audio_progress(interaction_for_restart, current_playing[2], current_playing[1]))
                          embed = create_embed(f"Гучність встановлено на {target_volume}%.")
                          await interaction.followup.send(embed=embed)
                     except Exception as e:
                          print(f"Error playing after reconnect {e}")
                          traceback.print_exc()
                          embed = create_embed(f"Виникла помилка: {e}")
                          await interaction.followup.send(embed=embed)

               else:
                 embed = create_embed("Помилка, нічого не грає.")
                 await interaction.followup.send(embed=embed)
            else:
                embed = create_embed("Ви не в голосовому каналі.")
                await interaction.followup.send(embed=embed)

        else:
          if voice_client.source:
                voice_client.source.volume = current_volume / 100.0
                embed = create_embed(f"Гучність встановлено на {target_volume}%.")
                await interaction.followup.send(embed=embed)
   else:
        embed = create_embed("Бот не підключений до голосового каналу")
        await interaction.followup.send(embed=embed)
async def update_message(message, content=None, embed=None):
    if isinstance(message, discord.WebhookMessage):
        await message.edit(content=content, embed=embed)
    else:
        await message.edit(content=content, embed=embed)