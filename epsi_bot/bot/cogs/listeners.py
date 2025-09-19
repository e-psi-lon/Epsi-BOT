import contextlib
import io
import traceback

import discord
from discord.ext import commands

from epsi_bot.bot.bot import Bot
from epsi_bot.utils import disconnect_from_channel, Server


class Listeners(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Listeners, doesn't contain any commands"

	@commands.Cog.listener("on_message")
	async def on_message(self, message: discord.Message) -> None:
		if not message.content.startswith("e!eval") or message.author.id != self.bot.owner_id:
			return
		
		try:
			code = message.content[6:].strip()
			if code.startswith('```py\n') and code.endswith('\n```'):
				code = code[6:-4]
			elif code.startswith('```python\n') and code.endswith('\n```'):
				code = code[10:-4]
			elif code.startswith('```\n') and code.endswith('\n```'):
				code = code[4:-4]
			elif code.startswith('```') and code.endswith('```'):
				code = code[3:-3]
			
			if not code:
				await message.reply("No code provided", delete_after=5)
				return
			
			# Prepare execution environment
			env = {
				'bot': self.bot,
				'message': message,
				'channel': message.channel,
				'author': message.author,
				'guild': message.guild,
				'discord': discord,
				'commands': commands,
			}
			
			output = io.StringIO()
			
			with contextlib.redirect_stdout(output):
				with contextlib.redirect_stderr(output):
					if '\n' not in code.strip():
						try:
							result = eval(code, env)
							if hasattr(result, '__await__'):
								result = await result
							if result is not None:
								output.write(repr(result))
						except SyntaxError:
							exec(code, env)
					else:
						indented_code = '\n'.join(['\t' + line for line in code.split('\n')])
						func_code = f"async def __ex():\n{indented_code}"
						exec(func_code, env)
						await env['__ex']()
			
			value = output.getvalue()
			if not value:
				value = "No output"
				
		except Exception as e:
			value = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
		
		# Split output if too long
		if len(value) > 1990:
			for chunk in [value[i:i+1990] for i in range(0, len(value), 1990)]:
				await message.reply(f"```py\n{chunk}\n```", delete_after=30)
		else:
			await message.reply(f"```py\n{value}\n```", delete_after=30)

	@commands.Cog.listener("on_voice_state_update")
	async def on_voice_state_update(self, _: discord.Member, before: discord.VoiceState,
	                                after: discord.VoiceState) -> None:
		"""Disconnect bot when it's alone in a voice channel"""
		
		async def check_and_disconnect(voice_state: discord.VoiceState) -> None:
			if (voice_state.channel is not None 
				and len(voice_state.channel.members) == 1 
				and voice_state.channel.members[0].id == self.bot.user.id):  # type: ignore[union-attr]
				await disconnect_from_channel(voice_state, self.bot)
				self.bot.logger.info(f"Bot disconnected from {voice_state.channel.name}, no more members in it")

		if after.channel is not None:
			await check_and_disconnect(after)
		if before.channel is not None:
			await check_and_disconnect(before)

	@commands.Cog.listener("on_guild_join")
	async def on_guild_join(self, guild: discord.Guild) -> None:
		channel = guild.system_channel
		text = 'Hey, I\'m a music bot in development made by ' \
		       '<@!708006478807695450>, I can play music from YouTube in a voice ' \
		       'channel. For now, I\'m not ready to use, which mean I\'m still under ' \
		       'test phase'
		if channel is not None:
			try:
				await channel.send(text)
			except discord.Forbidden:
				try:
					await guild.text_channels[0].send(text)
				except discord.Forbidden:
					pass
		else:
			try:
				await guild.text_channels[0].send(text)
			except discord.Forbidden:
				pass
		await Server.get_or_create(server_id=guild.id)


def setup(bot: Bot) -> None:
	bot.add_cog(Listeners(bot))
