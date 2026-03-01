from flask import Flask, render_template, request, flash, redirect, url_for, abort
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
login_manager = LoginManager()

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "login"

socketio = SocketIO(app, cors_allowed_origins="*")

#----------- DATABASE MODELS -----------

user_channels = db.Table(
    "user_channels",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("channel_id", db.Integer, db.ForeignKey("channel.id"), primary_key=True),
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    messages = db.relationship("Message", back_populates="user", cascade="all, delete-orphan")
    channels = db.relationship("Channel", secondary=user_channels, back_populates="users")
    owned_channels = db.relationship("Channel", back_populates="owner_user")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey("channel.id"), nullable=False)

    user = db.relationship("User", back_populates="messages")
    channel = db.relationship("Channel", back_populates="messages")

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner_user = db.relationship("User", back_populates="owned_channels")
    
    users = db.relationship("User", secondary=user_channels, back_populates="channels")
    messages = db.relationship("Message", back_populates="channel", cascade="all, delete-orphan")



@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

migrate = Migrate(app, db)


#----------- ROUTING EVENTS -----------

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        channel_name = request.form.get("channel_name")
        
        if not channel_name:
            flash("ONE OR MORE FIELDS MISSING")
            return redirect(url_for("index"))
        
        if len(channel_name) > 32:
            flash("CHANNEL NAME TOO LONG")
            return redirect(url_for("index"))
        
        new_channel = Channel(name=channel_name, owner_id=current_user.id )
        new_channel.users.append(current_user)
        
        db.session.add(new_channel)
        db.session.commit()

        flash("CHANNEL CREATED SUCCESSFULLY.")
        return redirect(url_for("index"))

    return render_template("index.html")

@app.route("/channel/<int:channel_id>", methods=["GET"])
@login_required
def channel(channel_id):
    channel = Channel.query.get(channel_id)

    if not channel:
        abort(404)
    
    if current_user not in channel.users:
        abort(403)

    messages = (Message.query.filter_by(channel_id=channel_id).order_by(Message.id.desc()).limit(50).all())
    messages.reverse()

    return render_template("channel.html", channel=channel, messages=messages)


@app.route("/logout", methods=["GET"])
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("ONE OR MORE FIELDS MISSING")
            return redirect(url_for("login"))

        user_check = User.query.filter_by(username=username).first()

        if not user_check or not check_password_hash(user_check.password_hash, password):
            flash("INVALID CREDENTIALS")
            return redirect(url_for("login"))
        
        login_user(user_check)
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/create_account", methods=["GET", "POST"])
def create_account():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not username or not password or not confirm_password:
            flash("ONE OR MORE FIELDS MISSING")
            return redirect(url_for("create_account"))

        elif password != confirm_password:
            flash("PASSWORDS DO NOT MATCH")
            return redirect(url_for("create_account"))
        
        user_check = User.query.filter_by(username=username).first()
        if user_check:
            flash("USERNAME ALREADY TAKEN")
            return redirect(url_for("create_account"))
        
        new_user = User(username = username, password_hash = generate_password_hash(password))
        
        db.session.add(new_user)
        db.session.commit()
        flash("ACCOUNT CREATED SUCCESSFULLY. PLEASE LOGIN.")
        return redirect(url_for("login"))

    return render_template("create_account.html")

#----------- SOCKET EVENTS -----------

@socketio.on("connect")
def handle_connect():
    if not current_user.is_authenticated:
        disconnect()
        return
    print("Client connected:", request.sid)


@socketio.on("join_channel")
def handle_join_channel(data):
    if not current_user.is_authenticated:
        disconnect()
        return
    
    channel_id = int(data.get("channel", 0))
    authorized = Channel.query.filter(Channel.id == channel_id, Channel.users.any(id=current_user.id)).first()
    if not authorized:
        return

    room = f"channel_{channel_id}"
    join_room(room)

    emit("server_message", {"username": current_user.username, "message": f" joined channel {channel_id}"}, to=room)


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected:", request.sid)


@socketio.on("send_message")
def handle_send_message(data):
    if not current_user.is_authenticated:
        return

    channel_id = int(data.get("channel", 0))
    msg = (data.get("message") or "").strip()
    if not channel_id or not msg:
        return

    room = f"channel_{channel_id}"

    rooms_for_sid = socketio.server.rooms(request.sid)
    if room not in rooms_for_sid:
        print("Blocked send (not in room):", request.sid, room)
        return

    new_message = Message(content=msg, user_id=current_user.id, channel_id=channel_id)
    db.session.add(new_message)
    db.session.commit()

    emit("receive_message", {
        "id": new_message.id,
        "channel": channel_id,
        "username": current_user.username,
        "message": new_message.content
    }, to=room)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)