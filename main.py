import datetime
import os
from dotenv import load_dotenv
from panel.panel import app

load_dotenv()

start_time = datetime.datetime.now()

if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    app.set_start_time(start_time)
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
