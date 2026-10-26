from quart import Blueprint, redirect, render_template, session, url_for
from werkzeug import Response

from epsi_bot.panel.panel_base import current_panel
from epsi_bot.panel.services.discord_api import get_user_data
from epsi_bot.utils.decorators import login_required

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
		token = session["token"]
		if "user" not in session:
			user = await get_user_data(token["access_token"])
			session["guilds"] = current_panel.bot.get_guilds_for(session["user_id"])
			session["user"] = user

		if session.get("guilds", None) is None:
			session["guilds"] = current_panel.bot.get_guilds_for(session["user_id"])

		current_panel.logger.debug(
			f"Showing panel with user:\n- {session['user']}\nwho has guilds:\n- {session['guilds']}"
		)
		return await render_template(
			"panel.html", servers=session["guilds"], user=session["user"]
		)

	return await _panel()
