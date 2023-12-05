import datetime
import multiprocessing
from multiprocessing.connection import Connection
import threading
import discord.utils
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

def start_app(conn: Connection, bot):
    from panel.panel import app
    app.set_bot(bot)
    app.run(host="0.0.0.0")
    conn.close()


class Bot(commands.Bot):
    async def on_ready(self):
        global start_time
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"/help | {len(self.guilds)} servers"))
        # pour pouvoir lancer le serveur web
        parent_conn, child_conn = multiprocessing.Pipe()
        p = multiprocessing.Process(target=start_app, args=(child_conn, self), name="Panel")
        p.start()

        # On verifie si on est sur main ou sur dev ou une autre branche
        if os.popen("git branch --show-current").read().strip() == "main":
            check_update()
            threading.Timer(18000, check_update).start()
        logging.info(f"Bot ready in {datetime.datetime.now() - start_time}")
        self.help_command = commands.DefaultHelpCommand()
        


bot = Bot(intents=discord.Intents.all())


@bot.slash_command(name="help", description="Affiche l'aide du bot", guild_ids=[812807444698549862])
async def _help(ctx):
    await ctx.response.defer()
    mapping = bot.get_bot_mapping()
    embeds = bot.send_bot_help(mapping)
    await ctx.respond(embeds=embeds)
    

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
    print(f"\033[0mScript started at {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} using python executable {sys.executable}")
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
        os.chdir("_others")
        os.system("python generate_db.py")
        os.chdir("..")
    start(bot)
