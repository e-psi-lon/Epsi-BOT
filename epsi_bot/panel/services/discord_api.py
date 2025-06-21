import asyncio
from quart import current_app, session
import aiohttp

from epsi_bot.utils import requests, UserData

async def get_user_data(access_token: str):
	"""Get user data from Discord API."""
	user = await requests.get(
		f"{current_app.config['API_ENDPOINT']}/users/@me",
		headers={"Authorization": f"Bearer {access_token}"}
	)
	return UserData.from_api_response(user)

async def token_from_code(code: str):
	"""Exchange authorization code for access token."""
	data = {
		"grant_type": "authorization_code",
		"code": code,
		"redirect_uri": current_app.config['REDIRECT_URI']
	}
	headers = {"Content-Type": "application/x-www-form-urlencoded"}

	return await requests.post(
		f"{current_app.config['API_ENDPOINT']}/oauth2/token",
		data=data,
		headers=headers,
		auth=aiohttp.BasicAuth(
			str(current_app.config['CLIENT_ID']),
			str(current_app.config['CLIENT_SECRET'])
		)
	)

async def refresh_token(token: str):
	"""Refresh an expired access token."""
	data = {
		"grant_type": "refresh_token",
		"refresh_token": token
	}
	headers = {"Content-Type": "application/x-www-form-urlencoded"}

	r = await requests.post(
		f"{current_app.config['API_ENDPOINT']}/oauth2/token",
		data=data,
		headers=headers,
		auth=aiohttp.BasicAuth(
			str(current_app.config['CLIENT_ID']),
			str(current_app.config['CLIENT_SECRET'])
		)
	)

	session['token'] = r
	user_id = session['user'].id
	session["user_id"] = user_id

	timer = asyncio.get_event_loop().call_later(
		session['token']['expires_in'],
		asyncio.get_event_loop().create_task,
		refresh_token(session['token']['refresh_token'])
	)
	current_app.timers[user_id] = timer
	return r

async def revoke_access_token(access_token: str):
	"""Revoke an access token."""
	data = {
		"token": access_token,
		"token_type_hint": "access_token"
	}
	headers = {"Content-Type": "application/x-www-form-urlencoded"}

	await requests.post(
		f"{current_app.config['API_ENDPOINT']}/oauth2/token/revoke",
		data=data,
		headers=headers,
		auth=aiohttp.BasicAuth(
			str(current_app.config['CLIENT_ID']),
			str(current_app.config['CLIENT_SECRET'])
		)
	)