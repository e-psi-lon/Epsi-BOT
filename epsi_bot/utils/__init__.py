"""
This module is the main module of the package utils. It contains all the classes, 
functions and constants that are used by the other modules. 
"""
from epsi_bot.utils.async_utils import (
	Event,
	run_async,
	run_sync,
	set_callback
)
from epsi_bot.utils.audio import (
	convert,
	disconnect_from_channel,
	finished_record_callback,
	get_index_from_title,
	get_lyrics,
	get_youtube,
	play_song
)
from epsi_bot.utils.autocomplete import (
	get_playlists,
	get_playlists_songs,
	get_queue_songs
)
from epsi_bot.utils.cache import (
	AudioCache,
	download,
	download_bulk
)
from epsi_bot.utils.constants import (
	EMBED_ERROR_BOT_NOT_CONNECTED,
	EMBED_ERROR_BOT_NOT_PLAYING,
	EMBED_ERROR_INDEX_TOO_HIGH,
	EMBED_ERROR_NAME_TOO_LONG,
	EMBED_ERROR_NO_RESULTS_FOUND,
	EMBED_ERROR_NOT_BOT_OWNER,
	EMBED_ERROR_PLAYLIST_EXISTS,
	EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST,
	EMBED_ERROR_QUEUE_EMPTY,
	EMBED_ERROR_VIDEO_TOO_LONG,
	GET_FILE_HTTP_URL,
	MAX_TRACK_LENGTH,
	OWNER_ID,
	YOUTUBE_CLIENT,
	YOUTUBE_REGEX
)
from epsi_bot.utils.decorators import (
	admin_required,
	login_required
)
from epsi_bot.utils.ipc import (
	IPCManager,
	IPCMessage,
	MessageType
)
from epsi_bot.utils.loggers import (
	CustomFormatter,
	get_logger,
	parse_args
)
from epsi_bot.utils.models import (
	Playlist,
	PlaylistReference,
	PlaylistSong,
	Queue,
	Server,
	ServerPlaylist,
	Song,
	SongListenCount,
	User,
	UserPlaylist,
	get_db_url
)
from epsi_bot.utils.panel_data import (
	ChannelData,
	ConfigData,
	GuildData,
	UserData
)
from epsi_bot.utils.type_utils import (
	FfmpegFormats,
	Sinks,
	type_checking
)
from epsi_bot.utils.views import Research

import epsi_bot.utils.requests as requests


__all__ = [
	# async_utils
	'Event',
	'run_async',
	'run_sync',
	'set_callback',
	
	# audio
	'convert',
	'disconnect_from_channel',
	'finished_record_callback',
	'get_index_from_title',
	'get_lyrics',
	'get_youtube',
	'play_song',
	
	# autocomplete
	'get_playlists',
	'get_playlists_songs',
	'get_queue_songs',
	
	# cache
	'AudioCache',
	'download',
	'download_bulk',
	
	# constants
	'EMBED_ERROR_BOT_NOT_CONNECTED',
	'EMBED_ERROR_BOT_NOT_PLAYING',
	'EMBED_ERROR_INDEX_TOO_HIGH',
	'EMBED_ERROR_NAME_TOO_LONG',
	'EMBED_ERROR_NO_RESULTS_FOUND',
	'EMBED_ERROR_NOT_BOT_OWNER',
	'EMBED_ERROR_PLAYLIST_EXISTS',
	'EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST',
	'EMBED_ERROR_QUEUE_EMPTY',
	'EMBED_ERROR_VIDEO_TOO_LONG',
	'GET_FILE_HTTP_URL',
	'MAX_TRACK_LENGTH',
	'OWNER_ID',
	'YOUTUBE_CLIENT',
	'YOUTUBE_REGEX',
	
	# decorators
	'admin_required',
	'login_required',
	
	# ipc
	'IPCManager',
	'IPCMessage',
	'MessageType',
	
	# loggers
	'CustomFormatter',
	'get_logger',
	'parse_args',
	
	# models
	'Playlist',
	'PlaylistReference',
	'PlaylistSong',
	'Queue',
	'Server',
	'ServerPlaylist',
	'Song',
	'SongListenCount',
	'User',
	'UserPlaylist',
	'get_db_url',
	
	# panel_data
	'ChannelData',
	'ConfigData',
	'GuildData',
	'UserData',
	
	# requests
	'requests',
	
	# type_utils
	'FfmpegFormats',
	'Sinks',
	'type_checking',
	
	# views
	'Research'
]