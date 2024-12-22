import time

async def on_voice_state_update(member, before, after, bot, players, music_queues, last_activity):
    if member == bot.user and before.channel and not after.channel:
        guild_id = before.channel.guild.id
        try:
           players.pop(guild_id, None)
           music_queues.pop(guild_id, None)
           last_activity.pop(guild_id, None)
           print(f"Бот було вигнано з голосового каналу на сервері {before.channel.guild.name}")
        except Exception as e:
          print(f"Помилка при відключенні бота на on_voice_state_update: {e}")
          import traceback
          traceback.print_exc()