import asyncio

import aiohttp
from quart import session

from epsi_bot.panel.panel_base import current_panel
from epsi_bot.utils import requests
from epsi_bot.utils.panel_data import UserData


async def get_user_data(access_token: str) -> UserData:
	"""Get user data from Discord API."""
	user = await requests.get(
		f"{current_panel.config['API_ENDPOINT']}/users/@me",
		headers={"Authorization": f"Bearer {access_token}"},
	)
	if not isinstance(user, dict):
		raise TypeError("Invalid user data received from Discord API")
	return UserData.from_api_response(user)


async def token_from_code(code: str) -> dict:
	"""Exchange authorization code for access token."""
	data = {
		"grant_type": "authorization_code",
		"code": code,
		"redirect_uri": current_panel.config["REDIRECT_URI"],
	}
	headers = {"Content-Type": "application/x-www-form-urlencoded"}

	r = await requests.post(
		f"{current_panel.config['API_ENDPOINT']}/oauth2/token",
		data=data,
		headers=headers,
		auth=aiohttp.BasicAuth(
			str(current_panel.config["CLIENT_ID"]),
			str(current_panel.config["CLIENT_SECRET"]),
		),
	)
	if not isinstance(r, dict):
		raise TypeError("Invalid token data received from Discord API")
	return r


async def refresh_token(token: str) -> dict:
	"""Refresh an expired access token."""
	data = {"grant_type": "refresh_token", "refresh_token": token}
	headers = {"Content-Type": "application/x-www-form-urlencoded"}

	r = await requests.post(
		f"{current_panel.config['API_ENDPOINT']}/oauth2/token",
		data=data,
		headers=headers,
		auth=aiohttp.BasicAuth(
			str(current_panel.config["CLIENT_ID"]),
			str(current_panel.config["CLIENT_SECRET"]),
		),
	)
	if not isinstance(r, dict):
		raise TypeError("Invalid token data received from Discord API")

	session["token"] = r
	user_id = session["user"].id
	session["user_id"] = user_id

	timer = asyncio.get_running_loop().call_later(
		session["token"]["expires_in"],
		asyncio.get_running_loop().create_task,
		refresh_token(session["token"]["refresh_token"]),
	)
	current_panel.timers[user_id] = timer
	return r


async def revoke_access_token(access_token: str) -> None:
	"""Revoke an access token."""
	data = {"token": access_token, "token_type_hint": "access_token"}
	headers = {"Content-Type": "application/x-www-form-urlencoded"}

	await requests.post(
		f"{current_panel.config['API_ENDPOINT']}/oauth2/token/revoke",
		data=data,
		headers=headers,
		auth=aiohttp.BasicAuth(
			str(current_panel.config["CLIENT_ID"]),
			str(current_panel.config["CLIENT_SECRET"]),
		),
	)
