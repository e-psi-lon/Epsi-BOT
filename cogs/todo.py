import re

import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands


class Todo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    todo = SlashCommandGroup(name="todo", description="Commands related to the to-do list",
                             guild_ids=[761485410596552736])

    @todo.command(name="add_line", description="Adds a line to the message")
    async def add_line(self, ctx: discord.ApplicationContext,
                       line: discord.Option(str, "The line to add", required=True),  # type: ignore
                       index: discord.Option(int, "The index of the line to add", required=False,
                                             default=None)):  # type: ignore
        await ctx.response.defer()
        if ctx.channel.id != 1128286383161745479:
            embed = discord.Embed(title="Ajout d'une ligne", description="Cette commande ne peut être utilisée que dans"
                                                                         " le channel <#1128286383161745479>",
                                  color=0xff0000)
            return await ctx.respond(embed=embed, delete_after=30)
        message = await ctx.channel.fetch_message(1128641774789861488)
        if index is None:
            index = len(message.embeds[0].fields) + 1
        lines = message.embeds[0].fields
        lines.insert(index - 1, discord.EmbedField(name=f"**`{index + 1}.`**", value=line, inline=False))
        for index_, line_ in enumerate(lines):
            line_.name = f"**`{index_ + 1}.`**"
        await message.edit(embed=discord.Embed(title="To-Do List", description="Les points suivant sont les "
                                                                               "différentes tâches à effectuer pour "
                                                                               "améliorer le bot", fields=lines))
        line = message.embeds[0].fields[index - 1]
        embed = discord.Embed(title="Ajout d'une ligne", description=f"La ligne {line.name} a été ajoutée au message "
                                                                     f"{message.jump_url}")
        await ctx.respond(embed=embed, delete_after=30)

    @todo.command(name="remove_line", description="Removes a line from the message")
    async def remove_line(self, ctx: discord.ApplicationContext,
                          index: discord.Option(int, "The index of the line to remove", required=True)):  # type: ignore
        await ctx.response.defer()
        if ctx.channel.id != 1128286383161745479:
            embed = discord.Embed(title="Suppression d'une ligne",
                                  description="Cette commande ne peut être utilisée que"
                                              " dans le channel <#1128286383161745479>",
                                  color=0xff0000)
            return await ctx.respond(embed=embed, delete_after=30)
        message = await ctx.channel.fetch_message(1128641774789861488)
        lines = message.embeds[0].fields
        old_line = lines.pop(index - 1)
        for index, line in enumerate(lines):
            line.name = f"**`{index + 1}.`**"
        await message.edit(embed=discord.Embed(title="To-Do List", description="Les points suivant sont les différentes"
                                                                               " tâches à effectuer pour améliorer"
                                                                               " le bot", fields=lines))
        embed = discord.Embed(title="Suppression d'une ligne", description=f"La ligne {old_line.name} a été "
                                                                           f"supprimée du message {message.jump_url}")
        await ctx.respond(embed=embed, delete_after=30)

    @todo.command(name="edit_line", description="Edits a line from the message")
    async def edit_line(self, ctx: discord.ApplicationContext, index: discord.Option(int,
                                                                                     "The index of the line to edit",
                                                                                     required=True),  # type: ignore
                        line: discord.Option(str, "The new line", required=True)):  # type: ignore
        await ctx.response.defer()
        if ctx.channel.id != 1128286383161745479:
            embed = discord.Embed(title="Modification d'une ligne", description="Cette commande ne peut être utilisée "
                                                                                "que dans le channel "
                                                                                "<#1128286383161745479>",
                                  color=0xff0000)
            return await ctx.respond(embed=embed, delete_after=30)
        message = await ctx.channel.fetch_message(1128641774789861488)
        lines = message.embeds[0].fields
        if " - Assigned to <@" in lines[index - 1].value:
            lines[index - 1].value = line + lines[index - 1].value[lines[index - 1].value.find(" - Assigned to <@"):]
        else:
            lines[index - 1].value = line
        await message.edit(embed=discord.Embed(title="To-Do List", description="Les points suivant sont les différentes"
                                                                               " tâches à effectuer pour améliorer"
                                                                               " le bot", fields=lines))
        line = message.embeds[0].fields[index - 1]
        embed = discord.Embed(title="Modification d'une ligne", description=f"La ligne {line.name} a"
                                                                            f" été modifiée dans le message"
                                                                            f" {message.jump_url}")
        await ctx.respond(embed=embed, delete_after=30)

    @todo.command(name="assign", description="Assigns a task to a user")
    async def assign(self, ctx: discord.ApplicationContext,
                     index: discord.Option(int, "The index of the line to assign", required=True),  # type: ignore
                     user: discord.Option(
                         discord.User, "The user to assign the task to", required=True)  # type: ignore
                     ):
        await ctx.response.defer()
        if ctx.channel.id != 1128286383161745479:
            embed = discord.Embed(title="Assignation d'une ligne", description="Cette commande ne peut être utilisée "
                                                                               "que dans le channel "
                                                                               "<#1128286383161745479>",
                                  color=0xff0000)
            return await ctx.respond(embed=embed, delete_after=30)
        message = await ctx.channel.fetch_message(1128641774789861488)
        lines: list[discord.EmbedField] = message.embeds[0].fields
        line: discord.EmbedField = lines[index - 1]
        regex1 = r' - Assigned to (.+)$'
        regex2 = r'<@(\d+)>'
        match_result = re.findall(regex1, line.value)
        if len(match_result) == 0:
            assigned_user = []
        else:
            match_result = match_result[0]
            assigned_user = re.findall(regex2, match_result).copy()
        if str(user.id) in assigned_user:
            embed = discord.Embed(title="Assignation d'une ligne",
                                  description=f"{user.mention} n'est plus assigné à la ligne {line.name} dans "
                                              f"le message {message.jump_url}")
            await ctx.respond(embed=embed, delete_after=30)
            assigned_user.remove(str(user.id))
        else:
            embed = discord.Embed(title="Assignation d'une ligne",
                                  description=f"{user.mention} est maintenant assigné à la ligne {line.name} dans le"
                                              f" message {message.jump_url}")
            await ctx.respond(embed=embed, delete_after=30)
            assigned_user.append(str(user.id))
        line.value = line.value[
                     :line.value.find(" - Assigned to <@")] if " - Assigned to <@" in line.value else line.value
        new_line = " - Assigned to "
        if len(assigned_user) == 0:
            new_line = ""
        elif len(assigned_user) == 1:
            new_line += f"<@{int(assigned_user[0])}>"
        elif len(assigned_user) == 2:
            new_line += f"<@{int(assigned_user[0])}> and <@{int(assigned_user[1])}>"
        else:
            for index, user_id in enumerate(assigned_user):
                if index == len(assigned_user) - 1:
                    new_line += f"and <@{int(user_id)}>"
                elif index == len(assigned_user) - 2:
                    new_line += f"<@{int(user_id)}> "
                else:
                    new_line += f"<@{int(user_id)}>, "
        line.value += new_line
        lines[index - 1] = line
        await message.edit(embed=discord.Embed(title="To-Do List",
                                               description="Les points suivant sont les différentes tâches à "
                                                           "effectuer pour améliorer le bot",
                                               fields=lines))
        line = message.embeds[0].fields[index - 1]

    @todo.command(name="tuto", description="Sends a tutorial on how to use the to-do list")
    async def tuto(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        embed = discord.Embed(title="Tutoriel",
                              description="Voici un tutoriel sur comment utiliser la to-do list, "
                                          "\"[...]\" signifie que le paramètre est optionnel et \"<...>\" signifie que "
                                          "le paramètre est obligatoire",
                              color=0x00ff00)
        embed.add_field(name="Ajouter une ligne",
                        value="Pour ajouter une ligne, utilisez la commande `/todo add_line <line:texte à écrire> "
                              "[index:index de l'élément]`",
                        inline=False)
        embed.add_field(name="Supprimer une ligne",
                        value="Pour supprimer une ligne, utilisez la commande `/todo remove_line "
                              "<index:index de l'élément>`",
                        inline=False)
        embed.add_field(name="Modifier une ligne",
                        value="Pour modifier une ligne, utilisez la commande `/todo edit_line <index:index de "
                              "l'élément> <line: nouveau texte>`",
                        inline=False)
        embed.add_field(name="Assigner une ligne",
                        value="Pour assigner une ligne, utilisez la commande `/todo assign <index:index de l'élément>"
                              " <user:utilisateur à assigné`",
                        inline=False)
        embed.add_field(name="Tutoriel", value="Pour afficher ce tutoriel, utilisez la commande `/todo tuto`",
                        inline=False)
        await ctx.respond(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Todo(bot))
