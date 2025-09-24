import asyncio
from quart import current_app, session
from typing import cast
import aiohttp

from epsi_bot.utils import requests, UserData
from epsi_bot.utils.protocols import PanelProtocol


async def get_user_data(access_token: str) -> UserData:
	"""Get user data from Discord API."""
	user = await requests.get(
		f"{current_app.config['API_ENDPOINT']}/users/@me",
		headers={"Authorization": f"Bearer {access_token}"},
	)
	if not isinstance(user, dict):
		raise ValueError("Invalid user data received from Discord API")
	return UserData.from_api_response(user)


async def token_from_code(code: str) -> dict:
	"""Exchange authorization code for access token."""
	data = {
		"grant_type": "authorization_code",
		"code": code,
		"redirect_uri": current_app.config["REDIRECT_URI"],
	}
	headers = {"Content-Type": "application/x-www-form-urlencoded"}

	r = await requests.post(
		f"{current_app.config['API_ENDPOINT']}/oauth2/token",
		data=data,
		headers=headers,
		auth=aiohttp.BasicAuth(
			str(current_app.config["CLIENT_ID"]),
			str(current_app.config["CLIENT_SECRET"]),
		),
	)
	if not isinstance(r, dict):
		raise ValueError("Invalid token data received from Discord API")
	return r


async def refresh_token(token: str) -> dict:
	"""Refresh an expired access token."""
	data = {"grant_type": "refresh_token", "refresh_token": token}
	headers = {"Content-Type": "application/x-www-form-urlencoded"}

	r = await requests.post(
		f"{current_app.config['API_ENDPOINT']}/oauth2/token",
		data=data,
		headers=headers,
		auth=aiohttp.BasicAuth(
			str(current_app.config["CLIENT_ID"]),
			str(current_app.config["CLIENT_SECRET"]),
		),
	)
	if not isinstance(r, dict):
		raise ValueError("Invalid token data received from Discord API")

	session["token"] = r
	user_id = session["user"].id
	session["user_id"] = user_id

	timer = asyncio.get_running_loop().call_later(
		session["token"]["expires_in"],
		asyncio.get_running_loop().create_task,
		refresh_token(session["token"]["refresh_token"]),
	)
	panel_app = cast(PanelProtocol, current_app)
	panel_app.timers[user_id] = timer
	return r


async def revoke_access_token(access_token: str) -> None:
	"""Revoke an access token."""
	data = {"token": access_token, "token_type_hint": "access_token"}
	headers = {"Content-Type": "application/x-www-form-urlencoded"}

	await requests.post(
		f"{current_app.config['API_ENDPOINT']}/oauth2/token/revoke",
		data=data,
		headers=headers,
		auth=aiohttp.BasicAuth(
			str(current_app.config["CLIENT_ID"]),
			str(current_app.config["CLIENT_SECRET"]),
		),
	)
