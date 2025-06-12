import pytest
from tortoise.exceptions import DoesNotExist

from epsi_bot.utils.models import Server, Asker, Song, Queue, Playlist, PlaylistSong, UserPlaylist


async def test_server_crud(db_fixture):
	# Create
	server = await Server.create(server_id=123456789)
	assert server.server_id == 123456789
	assert server.position == 0
	assert server.volume == 100
	assert not server.loop_queue
	assert not server.loop_song
	assert not server.random

	# Read
	fetched_server = await Server.get(server_id=123456789)
	assert fetched_server.server_id == server.server_id

	# Update
	await server.update_from_dict({"volume": 50, "loop_queue": True}).save()
	updated_server = await Server.get(server_id=123456789)
	assert updated_server.volume == 50
	assert updated_server.loop_queue

	# Delete
	await server.delete()
	with pytest.raises(DoesNotExist):
		await Server.get(server_id=123456789)


async def test_song_crud(db_fixture):
	# Create
	song = await Song.create(
		name="Test Song",
		url="https://youtube.com/watch?v=test"
	)
	assert song.name == "Test Song"
	assert song.url == "https://youtube.com/watch?v=test"

	# Read
	fetched_song = await Song.get(url="https://youtube.com/watch?v=test")
	assert fetched_song.name == song.name

	# Update
	await song.update_from_dict({"name": "Updated Song"}).save()
	updated_song = await Song.get(song_id=song.song_id)
	assert updated_song.name == "Updated Song"

	# Delete
	await song.delete()
	with pytest.raises(DoesNotExist):
		await Song.get(song_id=song.song_id)


async def test_playlist_crud(db_fixture):
	# Create
	playlist = await Playlist.create(name="Test Playlist")
	assert playlist.name == "Test Playlist"

	# Read
	fetched_playlist = await Playlist.get(playlist_id=playlist.playlist_id)
	assert fetched_playlist.name == playlist.name

	# Update
	await playlist.update_from_dict({"name": "Updated Playlist"}).save()
	updated_playlist = await Playlist.get(playlist_id=playlist.playlist_id)
	assert updated_playlist.name == "Updated Playlist"

	# Delete
	await playlist.delete()
	with pytest.raises(DoesNotExist):
		await Playlist.get(playlist_id=playlist.playlist_id)


async def test_user_crud(db_fixture):
	# Create
	asker = await Asker.create(discord_id=123456789)
	assert asker.discord_id == 123456789
	assert asker.asker_id is not None

	# Read
	fetched_asker = await Asker.get(discord_id=123456789)
	assert fetched_asker.discord_id == asker.discord_id

	# Update
	await asker.update_from_dict({"discord_id": 987654321}).save()
	updated_asker = await Asker.get(discord_id=987654321)
	assert updated_asker.discord_id == 987654321

	# Delete
	await asker.delete()
	with pytest.raises(DoesNotExist):
		await Asker.get(discord_id=asker.discord_id)


async def test_playlist_relationships(db_fixture):
	# Create test data
	playlist = await Playlist.create(name="Test Playlist")
	song = await Song.create(name="Test Song", url="https://test.com")
	asker = await Asker.create(discord_id=123456789)

	# Create playlist song relationship
	playlist_song = await PlaylistSong.create(
		playlist=playlist,
		song=song,
		asker=asker
	)

	# Test automatic position assignment
	assert playlist_song.position == 1

	# Test relationships
	await playlist.fetch_related("songs")
	assert len(playlist.songs) == 1
	assert playlist_song in playlist.songs


async def test_queue_position_auto_increment(db_fixture):
	server = await Server.create(server_id=123456789)
	song1 = await Song.create(name="Song 1", url="https://test1.com")
	song2 = await Song.create(name="Song 2", url="https://test2.com")
	asker = await Asker.create(discord_id=987654321)

	queue1 = await Queue.create(server=server, song=song1, asker=asker)
	queue2 = await Queue.create(server=server, song=song2, asker=asker)

	assert queue1.position == 1
	assert queue2.position == 2

	await server.fetch_related("queue")
	assert len(server.queue) == 2


async def test_user_playlist_relationships(db_fixture):
	# Create test data
	asker = await Asker.get(discord_id=123456789)
	playlist = await Playlist.create(name="Test Playlist")

	# Create user playlist relationship
	user_playlist = await UserPlaylist.create(
		asker=asker,
		playlist=playlist
	)

	# Test relationships
	await asker.fetch_related("playlists")
	assert len(asker.playlists) == 1
	assert user_playlist in asker.playlists
