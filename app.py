from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"

socketio = SocketIO(app, cors_allowed_origins="*")

# normal webpage route
@app.route("/")
def index():
    return render_template("index.html")


# when a browser connects
@socketio.on("connect")
def handle_connect():
    print("Client connected:", request.sid)
    emit("server_message", {"msg": "Connected to server"})


# when a browser disconnects
@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected:", request.sid)


# when client sends a chat message
@socketio.on("send_message")
def handle_send_message(data):
    """
    expected data:
    { "message": "hello world" }
    """

    print("Message received:", data)

    # broadcast to everyone
    emit("receive_message", data, broadcast=True)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)