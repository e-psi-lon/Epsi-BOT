from quart import Quart

from epsi_bot.panel.routes.admin import admin_bp
from epsi_bot.panel.routes.auth import auth_bp
from epsi_bot.panel.routes.main import main_bp
from epsi_bot.panel.routes.server import server_bp


def register_blueprints(app: Quart) -> None:
	"""Register all blueprints with the app."""
	app.register_blueprint(main_bp)
	app.register_blueprint(auth_bp)
	app.register_blueprint(server_bp)
	app.register_blueprint(admin_bp)
