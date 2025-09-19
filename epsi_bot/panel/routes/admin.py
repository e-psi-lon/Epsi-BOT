import datetime
import os
import psutil
from typing import cast, Any
from quart import Blueprint, render_template, request, websocket, current_app

from epsi_bot.utils import models, admin_required
from epsi_bot.utils.models import BaseModel
from epsi_bot.panel.services.cache import get_cache_stats
from epsi_bot.panel.helpers import format_table_info
from epsi_bot.panel.PanelProtocol import PanelProtocol

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
async def admin_panel() -> str:
	@admin_required
	async def _admin_panel() -> str:
		current_app.logger.info(f"Admin page requested by {request.remote_addr}")
		return await render_template('admin.html')

	return await _admin_panel()

@admin_bp.websocket('/')
async def admin_websocket() -> None:
	@admin_required
	async def _admin_websocket() -> None:
		panel_app = cast(PanelProtocol, current_app)
		panel_app.logger.info(f"Admin websocket requested by {websocket.remote_addr}")
		try:
			while True:
				message = await websocket.receive()
				if message == "refresh":
					data = await _get_admin_data()
					await websocket.send_json(data)
		except Exception as e:
			panel_app.logger.exception(e)
			await websocket.close(code=1001)

	return await _admin_websocket()

async def _get_admin_data() -> dict[str, Any]:
	panel_app = cast(PanelProtocol, current_app)
	# Get cache stats
	cache_stats: dict[str, str]
	if (stats := await get_cache_stats()) is None:
		cache_stats = {}
	else:
		cache_stats = {
			key.decode(): value.decode()
			for key, value in stats.items()
	}

	# Get process information
	current_process = psutil.Process(os.getpid())
	bot_process = psutil.Process(panel_app.bot_process.pid)
	start_time: datetime.datetime
	if panel_app.start_time is None:
		start_time = datetime.datetime.now()
	else:
		start_time = panel_app.start_time
	process_info = {
		"main": {
			"pid": current_process.pid,
			"cpu_percent": current_process.cpu_percent(interval=0.1),
			"memory_percent": current_process.memory_percent(),
			"memory_usage": current_process.memory_info().rss,
			"threads": len(current_process.threads()),
			"uptime": (datetime.datetime.now() - start_time).total_seconds()
		},
		"bot": {
			"pid": bot_process.pid,
			"cpu_percent": bot_process.cpu_percent(interval=0.1),
			"memory_percent": bot_process.memory_percent(),
			"memory_usage": bot_process.memory_info().rss,
			"voice_channels": await panel_app.get_from_bot("voice_channels"),
			"connected_servers": await panel_app.get_from_bot("connected_servers")
		}
	}

	# Get database information
	database = await _get_database_info()

	return {
		"cache_stats": cache_stats,
		"process_info": process_info,
		"database": database
	}

async def _get_database_info() -> dict[str, Any]:
	tables = [
		getattr(models, model_name)
		for model_name in models.__all__
		if (isinstance(getattr(models, model_name), type) and
		    issubclass(getattr(models, model_name), BaseModel) and
		    getattr(models, model_name) != BaseModel)
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
			k: v for k, v in table_data.items()
			if not (k.endswith("_id") and k[:-3] in table_data.keys())
		}

		database[table.__name__] = table_data

	return database
