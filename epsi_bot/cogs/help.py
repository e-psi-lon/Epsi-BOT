import discord
from discord.ext import commands, pages
from ..bot.bot import Bot

def format_params(cmd: discord.SlashCommand) -> str:
	params = []
	
	if not hasattr(cmd, 'options'):
		return ""
	
	for option in cmd.options:
		# Format as [param] if required, (param) if optional
		param_format = f"[{option.name}]" if option.required else f"({option.name})"
		params.append(param_format)
	
	return " `" + " ".join(params) + "`" if params else ""

def get_command_signature(cmd: discord.SlashCommand, parent: str) -> str:
	# Base command mention
	if hasattr(cmd, "qualified_id"):
		base = f"</{cmd.qualified_name}:{cmd.qualified_id}>"
	else:
		base = f"/{parent} {cmd.name}" if parent else f"/{cmd.name}"

	# Add formatted parameters
	return base + format_params(cmd)

def get_subcommands(cmd: discord.ApplicationCommand, parent: str = "") -> list[tuple[str, str]]:
	commands = []
	
	if isinstance(cmd, discord.commands.SlashCommandGroup):
		# For each subcommand in group
		for subcmd in cmd.subcommands:
			# Recursively get nested subcommands
			sub_cmds = get_subcommands(subcmd, f"{parent} {cmd.name}" if parent else cmd.name)
			commands.extend(sub_cmds)
	elif isinstance(cmd, discord.SlashCommand):
		# Base command - add to list
		commands.append((get_command_signature(cmd, parent), cmd.description or "No description provided"))
	else:
		raise ValueError(f"Unknown command type {type(cmd)}")
	return commands

class Help(commands.Cog):
	def __init__(self, bot: Bot):
		self.description = "Shows the help menu"
		self.bot = bot

	@commands.slash_command(name="help", description="Shows the help menu")
	async def help(self, ctx: discord.ApplicationContext):
		help_pages: list[discord.Embed | list[discord.Embed]] = []
		
		# Create main page
		main_page = discord.Embed(
			title="Bot Help",
			description="Use the buttons below to navigate through the help pages",
			color=discord.Color.blurple()
		)
		help_pages.append(main_page)

		# Generate pages for each cog
		for cog_name, cog in self.bot.cogs.items():
			# Skip hidden cogs
			if cog_name.startswith('_') or cog_name == "Help" or \
			(cog_name == "Admin" and ctx.author.id != self.bot.owner_id) or \
			(cog_name == "Todo" and ctx.channel.id != 1128286383161745479):
				continue
			
			# Get all commands for this cog
			cog_commands = []
			for cmd in cog.get_commands():
				cog_commands.extend(get_subcommands(cmd))
			if len(cog_commands) <= 25:
				# Single page case
				page = discord.Embed(
					title=f"{cog_name} Commands",
					color=discord.Color.blue()
				)
				for signature, description in cog_commands:
					page.add_field(
						name=signature,
						value=description,
						inline=False
					)
				page.set_footer(text="[name] = required, (name) = optional")
				help_pages.append(page)  # Add single Embed
			else:
				# Multiple pages case
				cog_pages = []
				for i in range(0, len(cog_commands), 25):
					page = discord.Embed(
						title=f"{cog_name} Commands (Page {i//25 + 1})",
						color=discord.Color.blue()
					)
					for signature, description in cog_commands[i:i+25]:
						page.add_field(
							name=signature,
							value=description,
							inline=False
						)
					page.set_footer(text="[name] = required, (name) = optional")
					cog_pages.append(page)
					help_pages.append(cog_pages)  # Add list of Embeds


		# Create and send paginator
		paginator = pages.Paginator(
			pages=help_pages,
			show_indicator=True,
			show_disabled=True,
			disable_on_timeout=True,
			timeout=180
		)
		
		await paginator.respond(ctx.interaction)
def setup(bot: Bot):
	bot.add_cog(Help(bot))