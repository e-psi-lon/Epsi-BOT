import asyncio

import aiohttp
from quart import Blueprint, redirect, request, session, url_for
from werkzeug import Response

from epsi_bot.panel.helpers import to_url
from epsi_bot.panel.panel_base import current_panel
from epsi_bot.panel.services.discord_api import (
	get_user_data,
	refresh_token,
	revoke_access_token,
	token_from_code,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login")
async def login() -> Response:
	return redirect(
		f"{current_panel.config['API_ENDPOINT']}/oauth2/authorize?"
		f"client_id={current_panel.config['CLIENT_ID']}&"
		f"redirect_uri={to_url(current_panel.config['REDIRECT_URI'])}&"
		f"response_type=code&scope=identify%20guilds"
	)


@auth_bp.route("/discord/callback")
async def callback() -> Response:
	code = request.args.get("code")
	if code is None:
		current_panel.logger.error("No code provided in callback request")
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
		current_panel.timers[user.id] = timer
		return redirect(url_for("main.panel"))
	except aiohttp.ClientResponseError:
		return redirect(url_for("main.index"))


@auth_bp.route("/logout")
async def logout() -> Response:
	if "token" in session:
		await revoke_access_token(session["token"]["access_token"])
		session.pop("token", None)

	session.pop("user", None)

	user_id = session.get("user_id")
	if user_id is not None and user_id in current_panel.timers:
		current_panel.timers[user_id].cancel()
		del current_panel.timers[user_id]

	session.pop("user_id", None)
	return redirect(url_for("main.index"))
