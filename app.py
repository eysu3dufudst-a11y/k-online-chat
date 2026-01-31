import os
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
import re

# Flask 앱 생성
app = Flask(__name__)
app.secret_key = "secret_key_here"  # 세션용

# SocketIO
import eventlet
eventlet.monkey_patch()
socketio = SocketIO(app)

# 업로드 설정
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'txt', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 간단한 사용자/방 데이터
users = {}  # username: password
rooms = ["General"]  # 기본 채팅방

# 검열용 단어 리스트
CENSORED_WORDS = ["badword1", "badword2"]

def censor_message(msg):
    for word in CENSORED_WORDS:
        msg = re.sub(word, "*" * len(word), msg, flags=re.IGNORECASE)
    return msg

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --------------------
# 라우트
# --------------------

@app.route("/")
def home():
    return redirect(url_for("login"))

# 로그인
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in users and users[username] == password:
            session['username'] = username
            return redirect(url_for("lobby"))
        return render_template("login.html", error="로그인 실패")
    return render_template("login.html")

# 회원가입
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in users:
            return render_template("register.html", error="이미 존재하는 사용자")
        users[username] = password
        session['username'] = username
        return redirect(url_for("lobby"))
    return render_template("register.html")

# 로비
@app.route("/lobby", methods=["GET", "POST"])
def lobby():
    if 'username' not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        new_room = request.form.get("room_name")
        if new_room and new_room not in rooms:
            rooms.append(new_room)
    return render_template("lobby.html", rooms=rooms, username=session['username'])

# 채팅방
@app.route("/chat/<room>")
def chat(room):
    if 'username' not in session or room not in rooms:
        return redirect(url_for("lobby"))
    return render_template("chat.html", room=room, username=session['username'])

# 파일 다운로드
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --------------------
# SocketIO 이벤트
# --------------------
@socketio.on("join")
def handle_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    emit("message", {"username": "System", "msg": f"{username}님이 입장했습니다."}, room=room)

@socketio.on("leave")
def handle_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    emit("message", {"username": "System", "msg": f"{username}님이 퇴장했습니다."}, room=room)

@socketio.on("send_message")
def handle_message(data):
    msg = censor_message(data['msg'])
    emit("message", {"username": data['username'], "msg": msg}, room=data['room'])

@socketio.on("send_file")
def handle_file(data):
    filename = secure_filename(data['filename'])
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, "wb") as f:
        f.write(data['file'])
    emit("file", {"username": data['username'], "filename": filename, "url": f"/uploads/{filename}"}, room=data['room'])

# --------------------
# 서버 실행 (Render 배포용)
# --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render가 제공하는 PORT 환경변수 사용
    socketio.run(app, host="0.0.0.0", port=port)
