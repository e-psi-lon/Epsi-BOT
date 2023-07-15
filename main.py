from classes import *
from utils import *
from discord.ext import commands
import discord
import os


class Bot(commands.Bot):
    async def on_ready(self):
        print(f'Logged in as {self.user.name}')


bot = Bot(intents=discord.Intents.all())



@bot.slash_command(name="help", description="Shows the help message")
async def help_command(ctx: discord.ApplicationContext):
    command_and_subcommand = [command.name for command in bot.application_commands if
                              isinstance(command, discord.SlashCommand)]
    command_and_subcommand.extend([f'{command.name} {subcommand.name}' for command in bot.application_commands if
                                   isinstance(command, discord.SlashCommandGroup) for subcommand in
                                   command.subcommands])
    embed = discord.Embed(title="Help", description=f"The help message. There are {len(command_and_subcommand)} commands",
                          color=0x00ff00)
    group = ""
    for command in bot.application_commands:
        if command.cog.__class__.__name__ != group:
                group = command.cog.__class__.__name__
                embed.add_field(name=f"__**{group if group != 'NoneType' else 'Not categorized'}**__", value=" ",
                                inline=False)
        if isinstance(command, discord.SlashCommandGroup):
            for subcommand in command.subcommands:
                embed.add_field(name=f"`/{command.name} {subcommand.name}`",
                                value=subcommand.description if subcommand.description is not None else "No description",
                                inline=True)
        elif isinstance(command, discord.SlashCommand):
        
            embed.add_field(name=f"`/{command.name}`",
                            value=command.description if command.description is not None else "No description",
                            inline=True)
        else:
            pass
    await ctx.respond(embed=embed)




def start(instance: Bot):
    # Charger les cogs
    if not os.path.exists('queue/'):
        os.mkdir('queue/')
    if not os.path.exists('audio/'):
        os.mkdir('audio/')
    cogs = [
        "cogs.channel",
        "cogs.others",
        "cogs.playlist",
        "cogs.queue_related",
        "cogs.state",
        "cogs.todo",
        "cogs.admin",

    ]
    for cog in cogs:
        instance.load_extension(cog)
    # Lancer le bot
    instance.run("MTEyODA3NDQ0Njk4NTQ5ODYyNA.G-kQRY.fuaCtflpY1SrNMJAS2fqixVMmwRUF7m2HRW6tw")


if __name__ == "__main__":
    start(bot)
