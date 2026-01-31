from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, join_room, leave_room, send
from werkzeug.utils import secure_filename
import os
import base64

# ------------------------------
# Flask 앱 설정
# ------------------------------
app = Flask(__name__)
app.secret_key = "supersecretkey"
socketio = SocketIO(app)

# 업로드 폴더
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ------------------------------
# 데이터 저장 (DB 미사용, 간단 예제)
# ------------------------------
users = {}      # {username: password}
rooms = ["General", "Tech", "Random"]  # 기본 채팅방
banned_words = ["나쁜말1","나쁜말2"]   # 검열 금칙어

# ------------------------------
# 루트 접속 → 로그인 페이지로 리다이렉트
# ------------------------------
@app.route("/")
def index():
    return redirect(url_for("login"))

# ------------------------------
# 로그인
# ------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in users and users[username] == password:
            session["username"] = username
            return redirect(url_for("lobby"))
        else:
            return render_template("login.html", error="아이디 또는 비밀번호가 잘못되었습니다.")
    return render_template("login.html")

# ------------------------------
# 회원가입
# ------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in users:
            return render_template("register.html", error="이미 존재하는 아이디입니다.")
        users[username] = password
        session["username"] = username
        return redirect(url_for("lobby"))
    return render_template("register.html")

# ------------------------------
# 로비 (채팅방 목록)
# ------------------------------
@app.route("/lobby")
def lobby():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("lobby.html", rooms=rooms, username=session["username"])

# ------------------------------
# 새 방 추가 (Ajax)
# ------------------------------
@app.route("/add_room", methods=["POST"])
def add_room():
    if "username" not in session:
        return "Unauthorized", 401
    data = request.get_json()
    room_name = data.get("room", "").strip()
    if room_name and room_name not in rooms:
        rooms.append(room_name)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

# ------------------------------
# 채팅방
# ------------------------------
@app.route("/chat/<room>")
def chat(room):
    if "username" not in session:
        return redirect(url_for("login"))
    if room not in rooms:
        return "존재하지 않는 방입니다."
    return render_template("chat.html", room=room, username=session["username"])

# ------------------------------
# 로그아웃
# ------------------------------
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

# ------------------------------
# SocketIO: 채팅
# ------------------------------
@socketio.on("join")
def handle_join(data):
    username = data["username"]
    room = data["room"]
    join_room(room)
    send({"username": "System", "msg": f"{username}님이 입장했습니다."}, to=room)

@socketio.on("message")
def handle_message(data):
    # 검열 처리
    msg = data.get("msg")
    if msg:
        for word in banned_words:
            msg = msg.replace(word, "****")
        data["msg"] = msg

    # 파일 처리
    file_data = data.get("file")
    if file_data:
        filename = secure_filename(file_data["name"])
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        # Base64 → 파일로 저장
        header, encoded = file_data["data"].split(",", 1)
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(encoded))
        # 클라이언트에서 접근할 수 있도록 URL 변경
        data["file"]["data"] = f"/uploads/{filename}"

    send(data, to=data["room"])

# ------------------------------
# 업로드 파일 서빙
# ------------------------------
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return app.send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ------------------------------
# 서버 실행
# ------------------------------
if __name__ == "__main__":
    socketio.run(app, debug=True)
