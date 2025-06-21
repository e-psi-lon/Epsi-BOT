from functools import wraps
from quart import session, redirect, url_for, request, websocket


__all__ = ["login_required", "admin_required"]

def login_required(f):
	"""Decorator to require user authentication."""
	@wraps(f)
	async def decorated_function(*args, **kwargs):
		if 'token' not in session:
			return redirect(url_for('auth.login'))
		return await f(*args, **kwargs)
	return decorated_function

def admin_required(f):
	"""Decorator to require admin access (local network only)."""
	@wraps(f)
	async def decorated_function(*args, **kwargs):
		# For regular routes
		if hasattr(request, 'remote_addr'):
			remote_addr = request.remote_addr
		# For websockets
		elif hasattr(websocket, 'remote_addr'):
			remote_addr = websocket.remote_addr
		else:
			return 403

		if not remote_addr.startswith("192.168.83.") and remote_addr != "127.0.0.1":
			return 403
		return await f(*args, **kwargs)
	return decorated_function