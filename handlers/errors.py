import discord
import traceback

async def on_app_command_error(interaction, error, bot):
    if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.followup.send(f"У вас недостатньо прав для використання цієї команди.", ephemeral=True)
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        remaining = round(error.retry_after)
        await interaction.followup.send(f"Зачекайте {remaining} секунд перш ніж виконувати команду", ephemeral=True)
    elif isinstance(error, discord.app_commands.BotMissingPermissions):
          needed_permissions = [permission for permission, has_permission in error.missing_permissions]
          if needed_permissions:
              await interaction.followup.send(f"Мені необхідні дозволи {', '.join(needed_permissions)}", ephemeral=True)
    elif isinstance(error, discord.app_commands.NoPrivateMessage):
           await interaction.followup.send("Ця команда не працює в особистих повідомленнях.", ephemeral=True)
    else:
            print(f"Виникла невідома помилка при обробці команди {interaction.command.name}:")
            traceback.print_exc()
            await interaction.followup.send(f"Виникла невідома помилка під час виконання команди.", ephemeral=True)