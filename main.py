import discord
from discord.ext import commands
import asyncio
from config import COMMAND_PREFIX, IDLE_TIMEOUT, YTDL_OPTS, FFMPEG_OPTS
from commands import music as music_commands
from commands import general as general_commands
from handlers import voice as voice_handlers
from handlers import errors as error_handlers
from music_logic import player as music_player
from music_logic import volume as volume_control
from dotenv import load_dotenv
import traceback
import os

load_dotenv()  # Завантажуємо змінні з .env

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("Токен бота не знайдено у файлі .env")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
players = {}
music_queues = {}
last_activity = {}
downloaded_files = {}
current_volume = 100.0

@bot.event
async def on_ready():
    print(f'Бот увійшов як {bot.user.name}')

    # Синхронізація дерева команд (global sync)
    try:
        synced = await bot.tree.sync()
        print(f"Синхронізовано {len(synced)} глобальних команд.")
    except Exception as e:
        print(f"Помилка під час глобальної синхронізації команд: {e}")

    # Sync in each guild (server) the bot is present in
    for guild in bot.guilds:
        try:
            synced = await bot.tree.sync(guild=guild)
            print(f"Синхронізовано {len(synced)} команд для серверу {guild.name}")
        except Exception as e:
            print(f"Помилка під час синхронізації команд для серверу {guild.name}: {e}")


@bot.event
async def on_voice_state_update(member, before, after):
    await voice_handlers.on_voice_state_update(member, before, after, bot, players, music_queues, last_activity)

@bot.tree.error
async def on_app_command_error(interaction, error):
   await error_handlers.on_app_command_error(interaction, error, bot)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        # Обробка натискання на кнопку
        if interaction.data and interaction.data.get('custom_id'):
            try:
                await interaction.response.defer()
                # Тут можна додати логіку обробки натискання на кнопку
                # Наприклад, виклик функції для відтворення обраного треку
                # або оновлення повідомлення
                print(f"Натиснуто кнопку з ID: {interaction.data['custom_id']}")
                # await interaction.followup.send(f"Вибрано трек {interaction.data['custom_id']}")
            except Exception as e:
                print(f"Error handling button interaction: {e}")
                traceback.print_exc()
                await interaction.followup.send("Виникла помилка при обробці натискання на кнопку.")
    
# Реєстрація команд з модулів
music_commands.register_commands(bot, music_queues, players, last_activity, current_volume)
general_commands.register_commands(bot, players, music_queues, last_activity)


# Додавання додаткової інформації з music_logic, до головного модуля (тимчасово, потрібно прибрати глобальний доступ)
music_player.music_queues = music_queues
music_player.players = players
music_player.last_activity = last_activity
music_player.bot = bot
music_player.current_volume = current_volume

volume_control.music_queues = music_queues
volume_control.players = players
volume_control.last_activity = last_activity
volume_control.bot = bot
volume_control.current_volume = current_volume


if __name__ == "__main__":
   bot.run(TOKEN)