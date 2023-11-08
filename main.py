import datetime
import threading
import discord.utils
from discord.ext.pages import Page, Paginator, PaginatorButton
from panel.panel import app
from utils import *
import os
import sys


def check_update():
    current_hash = os.popen("git rev-parse HEAD").read().strip()
    origin_hash = os.popen("git ls-remote origin main | awk '{print $1}'").read().strip()
    if current_hash != origin_hash:
        os.system("git pull")
        logging.info("Bot updated to the latest version")
        os.execl(sys.executable, sys.executable, *sys.argv)
    else:
        logging.info("Bot is already up to date")
    threading.Timer(18000, check_update).start()

class Bot(commands.Bot):
    async def on_ready(self):
        global start_time
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"/help | {len(self.guilds)} servers"))
        app.set_bot(self)
        # On deplace le processus du bot (le processus principal) dans un thread
        # pour pouvoir lancer le serveur web
        threading.Thread(target=app.run, name="Panel", kwargs={"host":"0.0.0.0"}).start()
        # On verifie si on est sur main ou sur dev ou une autre branche
        if os.popen("git branch --show-current").read().strip() == "main":
            check_update()
            threading.Timer(18000, check_update).start()
        logging.info(f"Bot ready in {datetime.datetime.now() - start_time}")
        


bot = Bot(intents=discord.Intents.all())


@bot.slash_command(name="help", description="Shows the help message")
async def help_command(ctx: discord.ApplicationContext):
    def get_commands(
            commands: list[discord.ApplicationCommand]
    ) -> list[dict[str: str | list | discord.SlashCommand]]:
        returned = []
        for command in commands:
            if command not in [command_['obj'] for command_ in returned]:
                if isinstance(command, discord.SlashCommand):
                    returned.append({"name": command.name, "description": command.description,
                                     "cog": command.cog.__class__.__name__ if command.cog is not None else "Uncategorized",
                                     "guilds": command.guild_ids if command.guild_ids is not None else [],
                                     "obj": command})
                if isinstance(command, discord.SlashCommandGroup):
                    returned.append({"name": command.name, "description": command.description,
                                     "cog": command.cog.__class__.__name__ if command.cog is not None else "Uncategorized",
                                     "guilds": command.guild_ids if command.guild_ids is not None else [],
                                     "obj": command, "kids": get_commands(command.subcommands)})
        return returned

    command_and_subcommand_list: list[dict[str: str | list | discord.ApplicationContext]] = get_commands(
        bot.application_commands)

    def get_kids(command: dict):
        returned = []
        if command.get("kids") is None:
            return []
        else:
            for kid in command["kids"]:
                if kid.get("kids") is None:
                    returned.append({"name": command['name'] + " " + kid['name'], "description": kid['description'],
                                     "cog": kid['cog'], "obj": kid['obj'],
                                     "guilds": kid['guilds'] if kid.get("guilds") != [] else command[
                                         'guilds'] if command.get("guilds") != [] else []})
                else:
                    returned.extend(get_kids(
                        {"name": command['name'] + " " + kid['name'], "description": kid['description'],
                         "cog": kid['cog'], "obj": kid['obj'], "kids": kid['kids'],
                         "guilds": kid['guilds'] if kid.get("guilds") != [] else command['guilds'] if command.get(
                             "guilds") != [] else []}))
        return returned

    showable_commands = []
    for command in command_and_subcommand_list:
        if command.get("kids") is None:
            showable_commands.append(command)
        else:
            showable_commands.extend(get_kids(command))
    # Remove commands that are not in the guild
    showable_commands = [command for command in showable_commands if
                         ctx.guild.id in command['guilds'] or command['guilds'] == []]
    cogs = []
    for command in showable_commands:
        if command["cog"] not in cogs:
            cogs.append(command["cog"])
    cogs.sort()
    sorted_command = [[command for command in showable_commands if command["cog"] == cog] for cog in cogs]
    pages = [discord.Embed(title="Help",
                           description="Choose a category using the buttons below. Here is the list of categories",
                           color=0x0000ff)]
    pages[0].add_field(name="__**Page 1 : Categories**__", value="This page", inline=False)
    for i, cog in enumerate(cogs):
        pages[0].add_field(name=f"__**Page {i + 2} : {cog}**__",
                           value=f"Use the button below to see the commands in the __**{cog}**__ category",
                           inline=False)
    for i in range(len(sorted_command)):
        if len(sorted_command[i]) == 0:
            continue
        if len(sorted_command[i]) <= 25:
            pages.append(discord.Embed(title="Help",
                                       description=f"Here is the list of commands for the __**{cogs[i]}**__ category",
                                       color=0x0000ff))
            for command in sorted_command[i]:
                if len(command['name'].split(" ")) == 1:
                    pages[-1].add_field(name=f"</{command['name']}:{command['obj'].id}>",
                                        value=command['description'] if command[
                                                                            'description'] != "" else "No description",
                                        inline=len(sorted_command[i]) > 15)
                else:
                    pages[-1].add_field(name=f"</{command['name']}:{command['obj'].qualified_id}>",
                                        value=command['description'] if command[
                                                                            'description'] != "" else "No description",
                                        inline=len(sorted_command[i]) > 15)
            pages[-1].set_footer(text=f"Showing {len(sorted_command[i])} commands")
        elif len(sorted_command) > 25:
            temp = []
            for j in range(len(sorted_command[i]) // 25):
                temp.append(discord.Embed(title="Help",
                                          description=f"Here is the list of commands for the __**{cogs[i]}**__ category (page {j + 1})",
                                          color=0x0000ff))
                for command in sorted_command[i][j * 25:(j + 1) * 25]:
                    if len(command['name'].split(" ")) == 1:
                        temp[-1].add_field(name=f"</{command['name']}:{command['obj'].id}>",
                                           value=command['description'] if command[
                                                                               'description'] != "" else "No description",
                                           inline=True)
                    else:
                        temp[-1].add_field(name=f"</{command['name']}:{command['obj'].qualified_id}>",
                                           value=command['description'] if command[
                                                                               'description'] != "" else "No description",
                                           inline=True)
                        temp[-1].set_footer(text=f"Showing {len(sorted_command[i]) - j * 25} commands")
            pages.extend(temp)

    buttons = [
        # The label is an emoji because it looks nice
        PaginatorButton("prev", style=discord.ButtonStyle.green, label="⬅️"),
        PaginatorButton("page_indicator", style=discord.ButtonStyle.grey, disabled=True),
        PaginatorButton("next", style=discord.ButtonStyle.green, label="➡️")
    ]
    paginator = Paginator([Page(embeds=[page]) for page in pages], use_default_buttons=False, custom_buttons=buttons)
    await paginator.respond(ctx.interaction)


def start(instance: Bot):
    # Charger les cogs
    global start_time
    if not os.path.exists('cache/'):
        os.mkdir('cache/')
    cogs = [
        "cogs.channel",
        "cogs.others",
        "cogs.playlist",
        "cogs.queue_related",
        "cogs.state",
        "cogs.todo",
        "cogs.admin",
        "cogs.listeners"
    ]
    os.system("cls" if os.name == "nt" else "clear")
    start_time = datetime.datetime.now()
    print(f"\033[0mScript started at {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    for cog in cogs:
        try:
            instance.load_extension(cog)
        except Exception as e:
            print(f"Failed to load extension {cog}")
            print(e)
    # Lancer l'instance du bot
    instance.run("MTEyODA3NDQ0Njk4NTQ5ODYyNA.G-kQRY.fuaCtflpY1SrNMJAS2fqixVMmwRUF7m2HRW6tw")


if __name__ == "__main__":
    # Les logs sont envoyés dans la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[console_handler])
    if not os.path.exists("database/database.db"):
        os.mkdir("database/")
        with open("database/database.db", "w") as f:
            f.write("")
        # On initialise la base de données avec "_others/generate_db.py", on se déplace dans le dossier "_others"
        os.chdir("_others")
        os.system("python generate_db.py")
        os.chdir("..")
    start(bot)
