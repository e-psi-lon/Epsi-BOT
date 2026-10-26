import datetime
import os
from typing import Any

import psutil
from quart import Blueprint, render_template, request, websocket

from epsi_bot.panel.helpers import format_table_info
from epsi_bot.panel.panel_base import current_panel
from epsi_bot.utils import models
from epsi_bot.utils.cache import get_cache_stats
from epsi_bot.utils.decorators import admin_required
from epsi_bot.utils.models import BaseModel

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
async def admin_panel() -> str:
	@admin_required
	async def _admin_panel() -> str:
		current_panel.logger.info(f"Admin page requested by {request.remote_addr}")
		return await render_template("admin.html")

	return await _admin_panel()


@admin_bp.websocket("/")
async def admin_websocket() -> None:
	@admin_required
	async def _admin_websocket() -> None:
		current_panel.logger.info(
			f"Admin websocket requested by {websocket.remote_addr}"
		)
		try:
			while True:
				message = await websocket.receive()
				if message == "refresh":
					data = await _get_admin_data()
					await websocket.send_json(data)
		except Exception:
			current_panel.logger.exception("Error in admin websocket:")
			await websocket.close(code=1001)

	return await _admin_websocket()


async def _get_admin_data() -> dict[str, Any]:
	# Get cache stats
	stats = await get_cache_stats()
	cache_stats = {key: str(value) for key, value in stats.items()}

	# Get process information
	current_process = psutil.Process(os.getpid())
	if current_panel.start_time is None:
		start_time = datetime.datetime.now(datetime.UTC)
	else:
		start_time = current_panel.start_time
	process_info = {
		"main": {
			"pid": current_process.pid,
			"cpu_percent": current_process.cpu_percent(interval=0.1),
			"memory_percent": current_process.memory_percent(),
			"memory_usage": current_process.memory_info().rss,
			"threads": len(current_process.threads()),
			"uptime": (
				datetime.datetime.now(datetime.UTC) - start_time
			).total_seconds(),
		},
		"bot": {
			"voice_channels": sum(
				1
				for guild in current_panel.bot.guilds
				for vc in guild.voice_channels
				if len(vc.members) > 0
			),
			"connected_servers": len(current_panel.bot.guilds),
		},
	}

	# Get database information
	database = await _get_database_info()

	return {
		"cache_stats": cache_stats,
		"process_info": process_info,
		"database": database,
	}


async def _get_database_info() -> dict[str, Any]:
	tables = [
		getattr(models, model_name)
		for model_name in models.__all__
		if (
			isinstance(getattr(models, model_name), type)
			and issubclass(getattr(models, model_name), BaseModel)
			and getattr(models, model_name) != BaseModel
		)
	]

	columns = {table: table._meta.fields_map for table in tables}
	formatted_columns = format_table_info(columns)
	database = {}

	for table, formatted_cols in formatted_columns.items():
		all_rows = await table.all()
		table_data = {}

		for col_name, col_type in formatted_cols.items():
			values = []
			for row in all_rows:
				value = getattr(row, col_name)
				if col_type:  # Primary key
					values.append(str(value))
				elif col_type is None:  # Foreign key
					values.append(str((await value).pk))
				else:  # Regular field
					if isinstance(value, datetime.datetime):
						values.append(value.strftime("%d/%m/%Y %H:%M:%S"))
					else:
						values.append(str(value))
			table_data[col_name] = (col_type, values)

		# Filter out foreign key ID fields when the FK object is present
		table_data = {
			k: v
			for k, v in table_data.items()
			if not (k.endswith("_id") and k[:-3] in table_data)
		}

		database[table.__name__] = table_data

	return database
