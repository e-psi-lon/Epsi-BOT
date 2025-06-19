
import asyncio
from unittest.mock import AsyncMock, MagicMock
from typing import Generator, AsyncGenerator

import discord
import discord.ext.commands
import pytest
from pytest_mock.plugin import MockerFixture
from tortoise import Tortoise

from epsi_bot.utils.models import Server, User, Song, Queue, Playlist


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
	"""Create an instance of the default event loop for the test session."""
	loop = asyncio.new_event_loop()
	yield loop
	loop.close()


@pytest.fixture(scope="session")
async def db_fixture() -> AsyncGenerator[None, None]:
	"""Initialize test database with in-memory SQLite."""
	await Tortoise.init(
		db_url='sqlite://:memory:',
		modules={'models': ['epsi_bot.utils.models']}
	)
	await Tortoise.generate_schemas()
	yield
	await Tortoise.close_connections()


@pytest.fixture
async def clean_db(db_fixture) -> AsyncGenerator[None, None]:
	"""Clean database before each test."""
	# Delete all records in reverse dependency order
	await Queue.all().delete()
	await Server.all().delete()
	await Song.all().delete()
	await User.all().delete()
	await Playlist.all().delete()
	yield
	# Cleanup after test
	await Queue.all().delete()
	await Server.all().delete()
	await Song.all().delete()
	await User.all().delete()
	await Playlist.all().delete()


@pytest.fixture
def mock_discord_user(mocker: MockerFixture) -> MagicMock:
	"""Create a mock Discord user."""
	user = mocker.MagicMock(spec=discord.User)
	user.id = 123456789
	user.name = "test_user"
	user.discriminator = "0000" # Discriminators are now deprecated in Discord
	user.display_name = "Test User"
	user.mention = f"<@{user.id}>"
	user.bot = False
	return user


@pytest.fixture
def mock_discord_member(mocker: MockerFixture, mock_discord_user) -> MagicMock:
	"""Create a mock Discord member."""
	member = mocker.MagicMock(spec=discord.Member)
	member.id = mock_discord_user.id
	member.name = mock_discord_user.name
	member.discriminator = mock_discord_user.discriminator
	member.display_name = mock_discord_user.display_name
	member.mention = mock_discord_user.mention
	member.bot = False
	member.guild = mocker.MagicMock(spec=discord.Guild)
	member.guild.id = 987654321
	member.voice = None  # Not in voice channel by default
	return member


@pytest.fixture
def mock_discord_guild(mocker: MockerFixture) -> MagicMock:
	"""Create a mock Discord guild."""
	guild = mocker.MagicMock(spec=discord.Guild)
	guild.id = 987654321
	guild.name = "Test Guild"
	guild.me = mocker.MagicMock(spec=discord.Member)
	guild.me.id = 111111111
	guild.voice_client = None
	return guild


@pytest.fixture
def mock_discord_channel(mocker: MockerFixture, mock_discord_guild) -> MagicMock:
	"""Create a mock Discord text channel."""
	channel = mocker.MagicMock(spec=discord.TextChannel)
	channel.id = 555555555
	channel.name = "test-channel"
	channel.guild = mock_discord_guild
	channel.send = AsyncMock()
	return channel


@pytest.fixture
def mock_voice_channel(mocker: MockerFixture, mock_discord_guild) -> MagicMock:
	"""Create a mock Discord voice channel."""
	voice_channel = mocker.MagicMock(spec=discord.VoiceChannel)
	voice_channel.id = 666666666
	voice_channel.name = "Test Voice"
	voice_channel.guild = mock_discord_guild
	voice_channel.connect = AsyncMock()
	return voice_channel


@pytest.fixture
def mock_voice_client(mocker: MockerFixture) -> MagicMock:
	"""Create a mock Discord voice client."""
	voice_client = mocker.MagicMock(spec=discord.VoiceClient)
	voice_client.is_connected.return_value = True
	voice_client.is_playing.return_value = False
	voice_client.is_paused.return_value = False
	voice_client.play = MagicMock()
	voice_client.pause = MagicMock()
	voice_client.resume = MagicMock()
	voice_client.stop = MagicMock()
	voice_client.disconnect = AsyncMock()
	return voice_client


@pytest.fixture
def mock_bot(mocker: MockerFixture, mock_discord_guild) -> MagicMock:
	"""Create a mock Discord bot."""
	bot = mocker.MagicMock(spec=discord.Bot)
	bot.user = mocker.MagicMock(spec=discord.ClientUser)
	bot.user.id = 111111111
	bot.user.name = "TestBot"
	bot.get_guild.return_value = mock_discord_guild
	bot.guilds = [mock_discord_guild]
	return bot


@pytest.fixture
async def mock_application_context(
		mocker: MockerFixture,
		mock_bot,
		mock_discord_guild,
		mock_discord_member,
		mock_discord_channel
) -> MagicMock:
	"""Create a mock Discord application context (for slash commands)."""
	ctx = mocker.MagicMock(spec=discord.ApplicationContext)
	ctx.bot = mock_bot
	ctx.guild = mock_discord_guild
	ctx.author = mock_discord_member
	ctx.user = mock_discord_member
	ctx.channel = mock_discord_channel
	ctx.respond = AsyncMock()
	ctx.send_followup = AsyncMock()
	ctx.edit = AsyncMock()
	ctx.defer = AsyncMock()
	return ctx


@pytest.fixture
async def mock_message_context(
		mocker: MockerFixture,
		mock_bot,
		mock_discord_guild,
		mock_discord_member,
		mock_discord_channel
) -> MagicMock:
	"""Create a mock Discord message context (for prefix commands)."""
	ctx = mocker.MagicMock(spec=discord.ext.commands.Context)
	ctx.bot = mock_bot
	ctx.guild = mock_discord_guild
	ctx.author = mock_discord_member
	ctx.channel = mock_discord_channel
	ctx.send = AsyncMock()
	ctx.reply = AsyncMock()
	return ctx


@pytest.fixture
async def sample_server(clean_db) -> Server:
	"""Create a sample server for testing."""
	return await Server.create(
		server_id=987654321,
		volume=100,
		position=0,
		loop_queue=False,
		loop_song=False,
		random=False
	)


@pytest.fixture
async def sample_user(clean_db) -> User:
	"""Create a sample user for testing."""
	return await User.create(discord_id=123456789)


@pytest.fixture
async def sample_song(clean_db) -> Song:
	"""Create a sample song for testing."""
	return await Song.create(
		name="Test Song",
		url="https://youtube.com/watch?v=test123",
		duration=180
	)


@pytest.fixture
async def sample_playlist(clean_db) -> Playlist:
	"""Create a sample playlist for testing."""
	return await Playlist.create(name="Test Playlist")


@pytest.fixture
def mock_youtube_dl(mocker: MockerFixture) -> MagicMock:
	"""Mock youtube-dl or yt-dlp functionality."""
	mock_extractor = mocker.patch('yt_dlp.YoutubeDL')
	mock_instance = mock_extractor.return_value
	mock_instance.extract_info.return_value = {
		'title': 'Test Song',
		'url': 'https://youtube.com/watch?v=test123',
		'duration': 180,
		'formats': [{'url': 'https://direct-audio-url.com/audio.m4a'}]
	}
	return mock_instance


@pytest.fixture
def mock_ffmpeg(mocker: MockerFixture) -> MagicMock:
	"""Mock FFmpeg audio source."""
	return mocker.patch('discord.FFmpegPCMAudio')


@pytest.fixture
async def bot_in_voice_channel(
		mock_application_context,
		mock_voice_channel,
		mock_voice_client,
		mock_discord_member
) -> tuple[MagicMock, MagicMock]:
	"""Setup bot connected to voice channel with user."""
	# User is in voice channel
	mock_discord_member.voice = MagicMock()
	mock_discord_member.voice.channel = mock_voice_channel

	# Bot is connected to the same voice channel
	mock_application_context.guild.voice_client = mock_voice_client
	mock_voice_client.channel = mock_voice_channel

	return mock_application_context, mock_voice_client


@pytest.fixture
def mock_async_timeout(mocker: MockerFixture) -> MagicMock:
	"""Mock asyncio timeout for testing timeout scenarios."""
	return mocker.patch('asyncio.wait_for')


# Pytest configuration
def pytest_configure(config):
	"""Configure pytest with custom markers."""
	config.addinivalue_line("markers", "asyncio: mark test as async")
	config.addinivalue_line("markers", "slow: mark test as slow running")
	config.addinivalue_line("markers", "integration: mark test as integration test")


# Custom assertions for Discord bot testing
class DiscordAssertions:
	"""Custom assertions for Discord bot testing."""

	@staticmethod
	def assert_embed_contains(embed: discord.Embed, title: str = None, description: str = None):
		"""Assert that embed contains expected content."""
		if title:
			assert embed.title == title
		if description:
			assert description in embed.description

	@staticmethod
	def assert_response_sent(mock_ctx: MagicMock, content: str = None):
		"""Assert that a response was sent to the context."""
		if hasattr(mock_ctx, 'respond'):
			mock_ctx.respond.assert_called()
		elif hasattr(mock_ctx, 'send'):
			mock_ctx.send.assert_called()

		if content:
			# Check if content is in any of the calls
			calls = mock_ctx.respond.call_args_list if hasattr(mock_ctx, 'respond') else mock_ctx.send.call_args_list
			assert any(content in str(call) for call in calls)


@pytest.fixture
def discord_assertions() -> DiscordAssertions:
	"""Provide custom Discord assertions."""
	return DiscordAssertions()
