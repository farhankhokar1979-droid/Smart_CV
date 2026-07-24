import os
os.environ["G_MESSAGES_DEBUG"] = ""
os.environ["PYTHONWARNINGS"] = "ignore"

import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug_mode)
