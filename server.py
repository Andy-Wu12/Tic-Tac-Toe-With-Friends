from flask import Flask, Response, request, render_template, redirect, flash, send_from_directory, url_for
from flask_login import login_user, logout_user, LoginManager, login_required, current_user, UserMixin
import pymongo
import json
import os
from bson.objectid import ObjectId
# File stuff
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import bcrypt
from flask_socketio import SocketIO, send, emit

# SERVER SETUP
app = Flask(__name__)
app.secret_key = os.urandom(24)
login_manager = LoginManager()
login_manager.login_view = 'getLogin'
login_manager.login_message = "This page requires you to login in order to access!"
login_manager.init_app(app)
socketio = SocketIO(app, logger=True)
# Image uploads
upload_dir = 'static/uploads/'
allowed_ext = {'png', 'jpg', 'jpeg'}
app.config['upload_dir'] = upload_dir
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
# connect to mongoDB
try:
    mongo = pymongo.MongoClient(host="db", port=27017, username='root', password = 'pass', serverSelectionTimeoutMS=1000)
    # mongo = pymongo.MongoClient(host="localhost", port=27017, serverSelectionTimeoutMS=1000)
    db = mongo.cse312
    mongo.server_info()  # triggers exception if cannot connect
except:
    print("ERROR - Cannot connect to MongoDB server: localhost:27017")


# USER CLASS
class User(UserMixin):
    def __init__(self, user):
        self.username = user["username"]
        self.email = user["email"]
        self.id = str(user["_id"])
        self.pic = str(user["profilePicture"])

    @login_manager.user_loader
    def load_user(user_id):
        return User(db.users.find({"_id": ObjectId(user_id)})[0])


# ROUTING
@app.route("/", methods=["GET"])
def getHome():
    try:
        return render_template("index.html")
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot read homepage"}),
            status=500,
            mimetype="application/json"
        )


@app.route("/login", methods=["GET"])
def getLogin():
    try:
        return render_template("login.html")
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot read homepage"}),
            status=500,
            mimetype="application/json"
        )


@app.route('/login', methods=["POST"])
def login():
    try:
        user = db.users.find({"email": request.form["email"]})
        if db.users.count_documents({"email": request.form["email"]}) != 1:
            flash('User does not exists. Did you mean to register?')
            return redirect("/login")
        if not bcrypt.checkpw(request.form["password"].encode("utf-8"), user[0]["password"]):
            flash('Invalid credentials.')
            return redirect("/login")
        dbResponse = db.users.update_one(
            {"_id": (user[0]["_id"])},
            {"$set": {"online": True}}
        )

        login_user(User(user=user[0]))
        wins = db.games.count_documents({"winner": user[0]["_id"]})
        socketio.emit("addUser", {"username": user[0]["username"], "id": str(user[0]["_id"]), "wins": wins}, broadcast=True)
        return redirect("/users")
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot login user"}),
            status=500,
            mimetype="application/json"
        )


@app.route('/logout', methods=["GET"])
@login_required
def logout():
    try:
        dbResponse = db.users.update_one(
                {"_id":ObjectId(current_user.get_id())},
                {"$set": {"online": False, "socketID": ""}},
            )
        socketio.emit("removeUser", {"id": current_user.get_id()}, broadcast=True)
        
        logout_user()
        return redirect("/")
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot logout user"}),
            status=500,
            mimetype="application/json"
        )


@app.route("/register", methods=["POST"])
def createUser():
    try:
        pw = request.form["password"].encode("utf-8")
        user = {"username": escape_html_input(request.form["username"]), "password": bcrypt.hashpw(pw, bcrypt.gensalt()), "online": True,
                "profilePicture": "", "email": escape_html_input(request.form["email"])}
        users = db.users.find({"email":escape_html_input(request.form["email"])})
        if db.users.count_documents({"email": escape_html_input(request.form["email"])}) != 0:
            flash('Email address already exists')
            return redirect("/register")
        dbResponse = db.users.insert_one(user)
        login_user(User(user=user))
        socketio.emit("addUser", {"username": user["username"], "id": str(user["_id"]), "wins": 0}, broadcast=True)
        return redirect("/users")
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot create user"}),
            status=500,
            mimetype="application/json"
        )


@app.route("/register", methods=["GET"])
def getRegister():
    try:
        return render_template("register.html")
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot read homepage"}),
            status=500,
            mimetype="application/json"
        )


@app.route("/dm/<recipientID>", methods=["GET"])
@login_required
def getDM(recipientID):
    try:
        users = db.users.find()
        recipient = db.users.find_one({"_id": ObjectId(recipientID)})
        current_user_doc = db.users.find_one({"_id": ObjectId(current_user.get_id())})
        # Find more efficient way to query "Sender" and "receiver" for BOTH IDS -- DONE
        messageCol = db.messages.find(
            {"$and": [
                {"sender": {"$in": [current_user.get_id(), recipientID]}},
                {"receiver": {"$in": [recipientID, current_user.get_id()]}}
            ]})
        # messages = db.messages.find()
        socketio.emit("connect")
        return render_template("dm.html", users=users, otherUser=recipient, messages=messageCol)
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot get messages"}),
            status=500,
            mimetype="application/json"
        )

# @app.route("/dm/<recipientID>", methods=["POST"])
@socketio.on('sendDM')
@login_required
def sendDM(_json):

    escaped_message = escape_html_input(_json["mess"])

    db.messages.insert_one({"sender": _json["sender"], "receiver": _json["receiver"],
                            "message": _json["mess"]})

    sender = db.users.find_one({"_id": ObjectId(_json["sender"])})
    recipient = db.users.find_one({"_id": ObjectId(_json["receiver"])})

    target_sid = recipient["socketID"]
    current_user_sid = sender["socketID"]

    # Emit to BOTH sender and receiver instead of refreshing page for sender
    socketio.emit("addDM", {"uid": str(recipient["_id"]), "sender_id": str(sender["_id"]),
                            "receive_id": str(recipient["_id"]), "message": escaped_message}, to=target_sid)
    socketio.emit("addDM", {"uid": str(current_user.get_id()), "sender_id": str(sender["_id"]),
                            "receive_id": str(recipient["_id"]), "message": escaped_message}, to=current_user_sid)

@app.route("/users", methods=["GET"])
@login_required
def getUserList():
    try:
        users = db.users.find({"online": True})
        return render_template("users.html", users=users, db=db.games)
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot get list of users!"}),
            status=500,
            mimetype="application/json"
        )

@app.route("/games", methods=["GET"])
@login_required
def getGameList():
    try:
        games = db.games.find({"active": False, "winner": ""})
        return render_template("gameList.html", games=games, db=db.users)
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot get list of games!"}),
            status=500,
            mimetype="application/json"
        )


@app.route("/profile/<id>", methods=["GET"])
@login_required
def getProfile(id):  # Sunset acts as default pic -- Check profile.html for template
    try:
        userDoc = db.users.find_one({"_id": ObjectId(id)})
        isCurrentUser = current_user.email == userDoc["email"]
        return render_template("profile.html", filename=userDoc["profilePicture"], username=userDoc["username"],
                               isCurrentUser=isCurrentUser)
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot get profile!"}),
            status=500,
            mimetype="application/json"
        )


@app.route("/profile", methods=["POST"])
@login_required
def updateProfile():  # Planning to implement delete of old profile picture from uploads dir
    try:
        # current_user.get_id() to get user ID, see logout for example
        # Modify profile picture
        # Referenced from https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
        if 'upload' not in request.files:
            flash('No upload in request!')
            return redirect("/profile")
        img = request.files['upload']
        if img and allowed_file(img.filename):
            # Combine file name and objectId to keep unique filename -- Find more secure way to do this if need be
            filename = secure_filename(current_user.get_id() + img.filename)
            img.save(os.path.join(app.config['upload_dir'], filename))
            dbResponse = db.users.update_one(
                {"_id": ObjectId(current_user.get_id())},
                {"$set": {"profilePicture": filename}}
            )
            return redirect(url_for('getProfile', id=current_user.get_id()))
    except RequestEntityTooLarge as ex:  # Possible exception due to line 20
        return Response(
            response=json.dumps({"message": "file upload too large! 16MB is the maximum size allowed."}),
            status=ex.code,  # 413 code @ https://github.com/pallets/werkzeug/blob/master/src/werkzeug/exceptions.py
            mimetype="application/json"
        )
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot update profile picture!"}),
            status=500,
            mimetype="application/json"
        )


# <filename> acts as an argument to the routed method
@app.route('/uploads/<filename>', methods=["GET"])
@login_required
def getImage(filename):
    try:
        return send_from_directory(upload_dir, filename=filename)
    except FileNotFoundError:
        return Response(
            response=json.dumps({"message": "cannot get profile picture!"}),
            status=500,
            mimetype="application/json"
        )


@app.route("/play/<gameID>", methods=["GET"])
@login_required
def getPlay(gameID):
    try:
        return render_template("play.html")
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot read homepage"}),
            status=500,
            mimetype="application/json"
        )

@app.route("/play", methods=["POST"])
@login_required
def createGame():
    try:
        game = {"player1": ObjectId(current_user.get_id()), "player2": "", "active": False,
        "winner": ""}
        dbResponse = db.games.insert_one(game)
        socketio.emit("addGame", {"username": current_user.username, "gameID": str(dbResponse.inserted_id)}, broadcast=True)
        return redirect(url_for('getPlay', gameID=dbResponse.inserted_id))
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot read homepage"}),
            status=500,
            mimetype="application/json"
        )

@app.route("/join/<gameID>", methods=["POST"])
@login_required
def joinGame(gameID):
    try:
        dbResponse = db.games.update_one(
            {"_id": ObjectId(gameID)},
            {"$set": {"player2": ObjectId(current_user.get_id()), "active": True}}
        )

        socketio.emit("removeGame", {"gameID": gameID}, broadcast=True)
        return redirect(url_for('getPlay', gameID=gameID))
    except Exception as ex:
        print(ex)
        return Response(
            response=json.dumps({"message": "cannot read homepage"}),
            status=500,
            mimetype="application/json"
        )

@socketio.on('registerID')
def updateUserWithWebsocketID(json):
    # update user with web socket id
    db.users.update_one(
        {"_id": ObjectId(current_user.get_id())},
        # {"$set": {"socketID": json["id"]}}
        # This is how the docs say to access personal "rooms". Not sure if the socket.id is the same
        {"$set": {"socketID": request.sid}}
    )

@socketio.on('getGameData')
def getGameData(json):
    game = db.games.find({"_id": ObjectId(json["id"])})[0]
    # update socketID
    db.users.update_one(
        {"_id": ObjectId(current_user.get_id())},
        {"$set": {"socketID": request.sid}}
    )
    if (game["active"]):
        emit("recieveGameData", {"opponent": str(game["player1"])}, to=request.sid)
        user = db.users.find({"_id": ObjectId(game["player1"])})[0]
        emit("opponenetJoined", {"opponent": str(game["player2"])}, to=user["socketID"])

@socketio.on('endTurn')
def endTurn(json):
    print(json)
    user = db.users.find({"_id": ObjectId(json["opponent"])})[0]
    emit("newTurn", {"move": json["moveLocation"]}, to=user["socketID"])

@socketio.on('wonGame')
def wonGame(json):
    # add winner to game, set to inactive
    db.games.update_one(
        {"_id": ObjectId(json["gameID"])},
        {"$set": {"winner": ObjectId(current_user.get_id()), "active": False}}
    )
    user = db.users.find({"_id": ObjectId(json["opponent"])})[0]
    emit("lostGame", {"move": json["moveLocation"]}, to=user["socketID"])

@socketio.on('tieGame')
def tieGame(json):
    # add winner to game, set to inactive
    db.games.update_one(
        {"_id": ObjectId(json["gameID"])},
        {"$set": {"winner": None, "active": False}}
    )
    user = db.users.find({"_id": ObjectId(json["opponent"])})[0]
    emit("gameTied", {"move": json["moveLocation"]}, to=user["socketID"])

# https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/ -- updateProfile()
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_ext

def escape_html_input(string):
    encoding_dict = {'&': '&amp;',
                     '<': '&lt;',
                     '>': '&gt;'}
    for k, v in encoding_dict.items():
        string = string.replace(k, v)
    return string


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
    socketio.run(app)
