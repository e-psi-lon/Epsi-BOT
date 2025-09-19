from quart import (
	Blueprint,
	session,
	redirect,
	url_for,
	render_template,
	request,
	current_app,
)
from werkzeug.wrappers.response import Response
from typing import cast

from epsi_bot.utils import models, ConfigData, get_youtube, YOUTUBE_REGEX
from epsi_bot.utils.decorators import login_required
from epsi_bot.panel.PanelProtocol import PanelProtocol

server_bp = Blueprint("server", __name__, url_prefix="/server")


@server_bp.route("/<int:server_id>", methods=["GET", "POST"])
async def server_detail(server_id: int) -> Response | str:
	@login_required
	async def _server_detail() -> Response | str:
		panel_app = cast(PanelProtocol, current_app)
		config = await models.Server.get_or_none(server_id=server_id)
		if (
			server_id not in [guild["id"] for guild in session.get("guilds", [])]
			or config is None
		):
			return redirect(url_for("main.panel"))

		if request.method == "POST":
			return await _handle_server_update(server_id, config)

		server_data = ConfigData(
			config.loop_song,
			config.loop_queue,
			config.random,
			config.position,
			await config.queue,
			server_id,
			(await panel_app.get_from_bot("guild", server_id=server_id)).name,
			config.volume,
		)
		return await render_template(
			"server.html",
			server=server_data,
			app=current_app,
			get_youtube=get_youtube,
			yt_regex=YOUTUBE_REGEX,
		)

	return await _server_detail()


async def _handle_server_update(server_id: int, config: models.Server) -> Response:
	values = (await request.form).to_dict()

	# Convert checkbox values to boolean
	for key, value in values.items():
		if isinstance(getattr(config, key, None), bool):
			values[key] = value == "on"

	# Update configuration
	if config.loop_song != values.get("loop_song"):
		config.loop_song = values["loop_song"]
	if config.loop_queue != values.get("loop_queue"):
		config.loop_queue = values["loop_queue"]
	if config.random != values.get("random"):
		config.random = values["random"]
	if config.position != values.get("position"):
		config.position = values["position"]

	# Handle queue updates
	if config.queue != values.get("queue"):
		await config.queue.all().delete()
		queue_data = values["queue"]

		await models.Song.bulk_create(
			[models.Song(name=song["title"], url=song["url"]) for song in queue_data],
			ignore_conflicts=True,
		)
		await models.User.bulk_create(
			[models.User(discord_id=song["user_id"]) for song in queue_data],
			ignore_conflicts=True,
		)
		await models.Queue.bulk_create(
			[
				models.Queue(
					server=config,
					song=await models.Song.get(name=song["title"]),
					asker=await models.User.get(discord_id=song["user_id"]),
				)
				for song in queue_data
			],
			ignore_conflicts=True,
		)

		await config.save()

	return redirect(url_for("server.server_detail", server_id=server_id))


@server_bp.route("/<int:server_id>/clear")
async def clear_queue(server_id: int) -> Response:
	@login_required
	async def _clear_queue() -> Response:
		config = await models.Server.get(server_id=server_id)
		await config.queue.all().delete()
		return redirect(url_for("server.server_detail", server_id=server_id))

	return await _clear_queue()


@server_bp.route("/<int:server_id>/add", methods=["POST"])
async def add_song(server_id: int) -> Response:
	@login_required
	async def _add_song() -> Response:
		config = await models.Server.get(server_id=server_id)
		form_data = await request.form

		song, _ = await models.Song.get_or_create(
			name=form_data["name"], url=form_data["url"]
		)
		user, _ = await models.User.get_or_create(discord_id=session["user"].id)

		queue_item = await models.Queue.create(server=config, song=song, asker=user)
		await queue_item.save()

		return redirect(url_for("server.server_detail", server_id=server_id))

	return await _add_song()
