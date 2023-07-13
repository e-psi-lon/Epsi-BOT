import discord
from discord.ext import commands


class Todo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="message", description="Sends a specific message")
    async def message(self, ctx: discord.ApplicationContext):
        message = await ctx.respond(embed=discord.Embed(title="To-Do list ", description="Les points suivant sont les différentes tâches à effectuer pour améliorer le bot"))
        # Enregister l'id du message afin de pouvoir l'utiliser dans les autres commandes (add_line, remove_line et edit_line)
        
    
    @commands.slash_command(name="add_line", description="Adds a line to the message")
    async def add_line(self, ctx: discord.ApplicationContext, line: discord.Option(str, "The line to add", required=True), index: discord.Option(int, "The index of the line to add", required=False, default=None)):
        message = await ctx.channel.fetch_message(1128641774789861488)
        if index is None:
            index = len(message.embeds[0].fields)+1
        lines = message.embeds[0].fields
        lines.insert(index-1, discord.EmbedField(name=f"**`{index+1}.`**", value=line, inline=False))
        for py_index, line in enumerate(lines):
            line.name = f"**`{py_index+1}.`**"
        await message.edit(embed=discord.Embed(title="To-Do List", description="Les points suivant sont les différentes tâches à effectuer pour améliorer le bot", fields=lines))
        line = message.embeds[0].fields[index-1]
        embed = discord.Embed(title="Ajout d'une ligne", description=f"La ligne {line.name} a été ajoutée au message {message.jump_url}")
        await ctx.respond(embed=embed, delete_after=5)
    
    @commands.slash_command(name="remove_line", description="Removes a line from the message")
    async def remove_line(self, ctx: discord.ApplicationContext, index: discord.Option(int, "The index of the line to remove", required=True)):
        message = await ctx.channel.fetch_message(1128641774789861488)
        lines = message.embeds[0].fields
        old_line = lines.pop(index-1)
        for index, line in enumerate(lines):
            line.name = f"**`{index+1}.`**"
        await message.edit(embed=discord.Embed(title="To-Do List", description="Les points suivant sont les différentes tâches à effectuer pour améliorer le bot", fields=lines))
        embed = discord.Embed(title="Suppression d'une ligne", description=f"La ligne {old_line.name} a été supprimée du message {message.jump_url}")
        await ctx.respond(embed=embed, delete_after=5)

    @commands.slash_command(name="edit_line", description="Edits a line from the message")
    async def edit_line(self, ctx: discord.ApplicationContext, index: discord.Option(int, "The index of the line to edit", required=True), line: discord.Option(str, "The new line", required=True)):
        message = await ctx.channel.fetch_message(1128641774789861488)
        lines = message.embeds[0].fields
        # Vérifier si la ligne contient déjà un utilisateur assigné
        if " - Assigned at <@" in lines[index-1].value:
            lines[index-1].value = line + lines[index-1].value[lines[index-1].value.find(" - Assigned at <@"):]
        else:
            lines[index-1].value = line
        await message.edit(embed=discord.Embed(title="To-Do List", description="Les points suivant sont les différentes tâches à effectuer pour améliorer le bot", fields=lines))
        line = message.embeds[0].fields[index-1]
        embed = discord.Embed(title="Modification d'une ligne", description=f"La ligne {line.name} a été modifiée dans le message {message.jump_url}")
        await ctx.respond(embed=embed, delete_after=5)
    
    @commands.slash_command(name="assign", description="Assigns a task to a user")
    async def assign(self, ctx: discord.ApplicationContext, index: discord.Option(int, "The index of the line to assign", required=True), user: discord.Option(discord.User, "The user to assign the task to", required=True)):
        message = await ctx.channel.fetch_message(1128641774789861488)
        lines = message.embeds[0].fields
        lines[index-1].value += f" - Assigned at {user.mention}"
        await message.edit(embed=discord.Embed(title="To-Do List", description="Les points suivant sont les différentes tâches à effectuer pour améliorer le bot", fields=lines))
        line = message.embeds[0].fields[index-1]
        embed = discord.Embed(title="Assignation d'une ligne", description=f"La ligne {line.name} a été assignée à {user.mention} dans le message {message.jump_url}")
        await ctx.respond(embed=embed, delete_after=5)

        

def setup(bot):
    bot.add_cog(Todo(bot))