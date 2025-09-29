from threading import Thread
from flask import Flask
import os

app = Flask(__name__)

@app.get("/")
def index():
    return "OK", 200

def start_server():
    port = int(os.environ.get("PORT", "8000"))
    Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
