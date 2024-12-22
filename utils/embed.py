import discord

def create_embed(title, description=None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(47, 49, 54)  # Колір фону
    )
    return embed