from flask import Flask, render_template, request, flash, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user
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

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()


#----------- ROUTING EVENTS -----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/logout", methods=["GET", "POST"])
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
    print("Client connected:", request.sid)
    emit("server_message", {"msg": "Connected to server"})


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected:", request.sid)


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