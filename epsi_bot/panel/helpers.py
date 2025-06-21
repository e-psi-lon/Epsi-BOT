from quart import Quart, render_template
import tortoise.fields.relational as relational
from tortoise import fields

from epsi_bot.utils.models import BaseModel

def to_url(url: str) -> str:
	"""URL encode a string."""
	return (url.replace(' ', '%20')
	        .replace('?', '%3F')
	        .replace('=', '%3D')
	        .replace('&', '%26')
	        .replace(':', '%3A')
	        .replace('/', '%2F')
	        .replace('+', '%2B')
	        .replace(',', '%2C')
	        .replace(';', '%3B')
	        .replace('@', '%40')
	        .replace('#', '%23'))

def format_table_info(
		tables_metadata: dict[type[BaseModel], dict[str, fields.Field]]
) -> dict[type[BaseModel], dict[str, bool | None]]:
	"""Format table metadata for display."""
	formatted = {}
	for table, columns in tables_metadata.items():
		formatted[table] = {
			name: (True if col.pk
			       else None if isinstance(col, relational.ForeignKeyFieldInstance)
			else False)
			for name, col in columns.items()
			if not isinstance(col, relational.BackwardFKRelation)
		}
	return formatted

def register_error_handlers(app: Quart):
	"""Register error handlers for the application."""
	for code in range(400, 500):
		try:
			@app.errorhandler(code)
			async def _error_page(e):
				if e.name == "NotFound":
					return 404
				return await render_template('error.html', code=code), code
		except ValueError:
			continue