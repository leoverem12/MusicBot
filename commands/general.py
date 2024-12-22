import discord
from discord import app_commands
from utils.embed import create_embed

def register_commands(bot, players, music_queues, last_activity):
   @bot.tree.command(name='volume', description='Змінює гучність відтворення.')
   @app_commands.describe(level='Рівень гучності (0-1000)')
   async def volume(interaction: discord.Interaction, level: str):
      from music_logic import volume
      await volume.volume(interaction, level)

   @bot.tree.command(name='stop', description='Зупиняє відтворення і виходить з голосового каналу.')
   async def stop(interaction: discord.Interaction):
      from music_logic import player
      await player.stop(interaction)

   @bot.tree.command(name='join', description='Приєднується до голосового каналу.')
   async def join(interaction: discord.Interaction):
         from music_logic import player
         await player.join(interaction)

   @bot.tree.command(name='shutdown', description='Завершує роботу бота (потрібні права адміністратора).')
   @app_commands.checks.has_permissions(administrator=True)
   async def shutdown(interaction: discord.Interaction):
       from music_logic import player
       await player.shutdown(interaction)