from typing import cast

from quart import Blueprint, current_app, redirect, render_template, session, url_for
from werkzeug import Response

from epsi_bot.panel.services.discord_api import get_user_data
from epsi_bot.utils.decorators import login_required
from epsi_bot.utils.protocols import PanelProtocol

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
async def index() -> Response | str:
	if "token" in session:
		return redirect(url_for("main.panel"))
	return await render_template("index.html")


@main_bp.route("/panel")
async def panel() -> Response | str:
	@login_required
	async def _panel() -> Response | str:
		panel_app = cast(PanelProtocol, current_app)
		token = session["token"]
		if "user" not in session:
			user = await get_user_data(token["access_token"])
			session["guilds"] = await panel_app.ipc.request(
				"guilds", user_id=session["user_id"]
			)
			session["user"] = user

		if session.get("guilds", None) is None:
			session["guilds"] = await panel_app.ipc.request(
				"guilds", user_id=session["user_id"]
			)

		panel_app.logger.debug(
			f"Showing panel with user:\n- {session['user']}\nwho has guilds:\n- {session['guilds']}"
		)
		return await render_template(
			"panel.html", servers=session["guilds"], user=session["user"]
		)

	return await _panel()
