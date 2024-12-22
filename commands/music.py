import discord
from discord import app_commands
from music_logic import player as music_player

def register_commands(bot, music_queues, players, last_activity, current_volume):

   @bot.tree.command(name='play', description='Відтворює аудіо з YouTube або додає до черги.')
   @app_commands.describe(search_term='Пошуковий запит або URL')
   async def play(interaction: discord.Interaction, search_term: str):
       await music_player.play(interaction, search_term)

   @bot.tree.command(name='skip', description='Пропускає поточну пісню.')
   async def skip(interaction: discord.Interaction):
       await music_player.skip(interaction)
   
   @bot.tree.command(name='pause', description='Призупиняє відтворення.')
   async def pause(interaction: discord.Interaction):
        await music_player.pause(interaction)

   @bot.tree.command(name='resume', description='Відновлює відтворення.')
   async def resume(interaction: discord.Interaction):
      await music_player.resume(interaction)
   
   @bot.tree.command(name='playlist', description='НЕ ВИКОРИСТОВУЙТЕ ЦЕ!! ВОНО БА')
   async def playlist(interaction: discord.Interaction):
        # await music_player.playlist(interaction)
        pass