import asyncio

import discord
import pytest
from pytest_mock.plugin import MockerFixture
from tortoise import Tortoise


@pytest.fixture(scope="session")
def event_loop():
	loop = asyncio.new_event_loop()
	yield loop
	loop.close()


@pytest.fixture(scope="session")
async def db_fixture():
	await Tortoise.init(
		db_url='sqlite://:memory:',
		modules={'models': ['epsi_bot.utils.models']}
	)
	await Tortoise.generate_schemas()
	yield
	await Tortoise.close_connections()


@pytest.fixture
def bot(mocker):
	pass


@pytest.fixture
async def ctx(mocker: MockerFixture):
	ctx = mocker.MagicMock(spec=discord.ApplicationContext)
	mocker.patch.object(ctx, "guild", spec=discord.Guild)
