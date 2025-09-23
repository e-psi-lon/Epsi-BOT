import asyncio
from quart import Blueprint, request, session, redirect, url_for, current_app
import aiohttp
from typing import cast

from werkzeug import Response

from epsi_bot.panel.services.discord_api import (
	token_from_code,
	refresh_token,
	revoke_access_token,
)
from epsi_bot.panel.helpers import to_url
from epsi_bot.panel.services.discord_api import get_user_data
from epsi_bot.panel.PanelProtocol import PanelProtocol

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login")
async def login() -> Response:
	return redirect(
		f"{current_app.config['API_ENDPOINT']}/oauth2/authorize?"
		f"client_id={current_app.config['CLIENT_ID']}&"
		f"redirect_uri={to_url(current_app.config['REDIRECT_URI'])}&"
		f"response_type=code&scope=identify%20guilds"
	)


@auth_bp.route("/discord/callback")
async def callback() -> Response:
	panel_app = cast(PanelProtocol, current_app)
	code = request.args.get("code")
	if code is None:
		panel_app.logger.error("No code provided in callback request")
		return redirect(url_for("main.index"))
	try:
		token = await token_from_code(code)
		timer = asyncio.get_running_loop().call_later(
			token["expires_in"],
			asyncio.get_running_loop().create_task,
			refresh_token(token["refresh_token"]),
		)
		session["token"] = token

		user = await get_user_data(token["access_token"])
		session["user_id"] = user.id
		panel_app.timers[user.id] = timer
		return redirect(url_for("main.panel"))
	except aiohttp.ClientResponseError:
		return redirect(url_for("main.index"))


@auth_bp.route("/logout")
async def logout() -> Response:
	panel_app = cast(PanelProtocol, current_app)
	if "token" in session:
		await revoke_access_token(session["token"]["access_token"])
		session.pop("token", None)

	session.pop("user", None)

	user_id = session.get("user_id")
	if user_id and user_id in panel_app.timers:
		panel_app.timers[user_id].cancel()
		del panel_app.timers[user_id]

	session.pop("user_id", None)
	return redirect(url_for("main.index"))
