""" The Tagged Server Side

APIS:
    admin_clear

    tags_all
    tags_open

    notes_all
    notes_recover
    notes_open
        write_unlock
    notes_delete

    notes_save
    notes_create
"""
from flask import Flask, request, session
from flask_jsonpify import jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import time
import json

app = Flask('tagged')
client = MongoClient()
db = client['tagged']

### Service Functions
def get_user():
    user = db.users.find_one({'_id': ObjectId(session['userID'])})
    return user

def get_tag_name_IDs():
    user = get_user()
    tag_name_IDs = {}
    for tagID in user['tagIDs']:
        tag = db.tags.find_one({'_id': tagID})
        tag_name_IDs[tag['name']] = tag['_id']
    return tag_name_IDs

def create_note_tags(tag_names):
    tag_name_IDs = get_tag_name_IDs()
    for tag_name in tag_names:
        if tag_name in tag_name_IDs:
                db.tags.update_one({"_id": tag_name_IDs[tag_name]},
                        {"$push":{"noteIDs":ObjectId(session['current_note_objectID'])}})
        else:
                tag = {}
                tag['name'] = tag_name
                tag['noteIDs'] = [ObjectId(session['current_note_objectID'])]
                tagID = db.tags.insert_one(tag).inserted_id
                db.users.update_one({"_id": ObjectId(session['userID'])},
                        {"$push":{"tagIDs": tagID}})

def delete_note_tags(tag_names):
    tag_name_IDs = get_tag_name_IDs()
    for tag_name in tag_names:
        tag = db.tags.find_one({"_id": tag_name_IDs[tag_name]})
        tag['noteIDs'].remove(ObjectId(session['current_note_objectID']))
        tagID = tag_name_IDs[tag_name]
        if not tag['noteIDs']:
            db.tags.delete_one({"_id": tagID})
            db.users.update_one({"_id": ObjectId(session['userID'])},
                    {"$pull":{"tagIDs": tagID}})
        else:
            db.tags.update_one({"_id": tagID}, {"$set": tag})

def update_session(username, userID):
    session['username'] = username
    session['userID'] = userID
    session['current_note_objectID'] = None
    session['current_tag_objectID'] = None
    session['write_lock'] = False

def get_current_note_objectID():
    return session['current_note_objectID']

def request_invalid():
    if 'username' not in session:
        return True
    else:
        return False

### Request Functions
def jsonp_succeed():
    return jsonify({"status":"succeed"})

def jsonp_failed():
    return jsonify({"status":"failed"})

@app.route('/users/signin')
def users_signin():
    username = request.args.get('username')
    password = request.args.get('password')
    user = db.users.find_one({'username': username})
    if user['password'] == password:
        update_session(username, str(user['_id']))
        return jsonp_succeed()
    else:
        return jsonp_failed()

@app.route('/users/signup')
def users_signup():
    username = request.args.get('username')
    password = request.args.get('password')
    if db.users.find_one({'username': username}):
        return jsonp_failed()
    else:
        userID = db.users.insert_one({
            "username": username,
            "password": password,
            "tagIDs": [],
            "noteIDs": []
        }).inserted_id
        update_session(username, str(userID))
        return jsonp_succeed()

@app.route('/users/signout')
def users_signout():
    session.pop('username', None)
    session.pop('userID', None)
    session.pop('current_note_objectID', None)
    session.pop('current_tag_objectID', None)
    session.pop('write_lock', None)
    return jsonp_succeed()

@app.route('/notes/unlock')
def write_unlock():
    session['write_lock'] = False
    return jsonp_succeed()

@app.route('/tags/all')
def tags_all():
    def get_user_tags():
        user = get_user()
        tags = []
        for tagID in user['tagIDs']:
            tag = db.tags.find_one({'_id': tagID})
            tags.append(tag)
        return tags
    if request_invalid():
        return jsonp_failed()

    items = []
    tags = get_user_tags()
    for tag in tags:
        item = {}
        item['name'] = tag['name']
        item['objectID'] = str(tag['_id'])
        items.append(item)

    return jsonify({"items":items})

@app.route('/tags/open')
def tags_open():
    if request_invalid():
        return jsonp_failed()

    objectID_str = request.args.get('objectID')
    if objectID_str == "":
        session['current_tag_objectID'] = None
    else:
        session['current_tag_objectID'] = objectID_str
    return jsonp_succeed()

@app.route('/notes/all')
def notes_all():
    def get_user_notes():
        notes = []
        user = get_user()
        for noteID in user['noteIDs']:
            note = db.notes.find_one({"_id": noteID})
            notes.append(note)
        return notes
    def get_note_des(note):
        des_str = ""
        for line in note['lines']:
            if line['type'] != "h1":
                for char in line['raw']:
                    des_str += char
                    if len(des_str) >= 200:
                        return des_str
                des_str += " "
        return des_str
    if request_invalid():
        return jsonp_failed()
    # notes
    if session['current_tag_objectID']:
        notes = []
        tag = db.tags.find_one({"_id": ObjectId(session['current_tag_objectID'])})
        for noteID in tag['noteIDs']:
            note = db.notes.find_one({"_id": noteID})
            notes.append(note)
    else:
        notes = get_user_notes()

    # items 
    items = []
    for note in notes:
        item = {}
        item['title'] = note['title']
        item['des'] = get_note_des(note)
        item['objectID'] = str(note['_id'])
        items.append(item)

    # tag_name 
    if session['current_tag_objectID'] == None:
        tag_name = "Notes"
    else:
        tag = db.tags.find_one({"_id": ObjectId(session['current_tag_objectID'])})
        tag_name = "#" + tag['name']

    if session['current_note_objectID'] == None:
        return jsonify({"items":items, "tag_name":tag_name})
    else:
        return jsonify({"items":items, "tag_name":tag_name, "current_objectID":session['current_note_objectID']})

@app.route('/notes/create')
def notes_create():
    if request_invalid():
        return jsonp_failed()
    session['current_note_objectID'] = None
    session['write_lock'] = True
    return jsonp_succeed()

@app.route('/notes/open')
def notes_open():
    if request_invalid():
        return jsonp_failed()
    session['write_lock'] = True
    session['current_note_objectID'] = request.args.get('objectID')
    return jsonp_succeed()

@app.route('/notes/load')
def notes_load():
    if request_invalid():
        return jsonp_failed()
    if session['current_note_objectID'] == None:
        return jsonify({
            "lines":[{"type":"", "text":"", "raw":""}],
            "current_line":0,
            "maximum_line":0,
            "tags":""
        })
    else:
        lines = db.notes.find_one({"_id":ObjectId(session['current_note_objectID'])})
        return jsonify({
            "lines": lines['lines'],
            "current_line": lines['current_line'],
            "maximum_line": lines['maximum_line'],
            "title": lines['title'],
            "tags": lines['tags'] if 'tags' in lines else ""
        })



@app.route('/notes/save')
def notes_save():
    if request_invalid():
        return jsonp_failed()
    if session['write_lock']:
        return jsonp_failed()
    
    if session['current_note_objectID'] != None:
        if request.args.get('tags') == "null":
            tags = []
        else:
            tags = json.loads(request.args.get('tags'))

        lines = db.notes.find_one({"_id":ObjectId(session['current_note_objectID'])})

        if 'tags' in lines:
            delete_tags = list(set(lines['tags']) - set(tags))
        else:
            delete_tags = []
        delete_note_tags(delete_tags)

        if 'tags' in lines:
            create_tags = list(set(tags) - set(lines['tags']))
        else:
            create_tags = tags
        create_note_tags(create_tags)

        db.notes.update_one(
            {"_id": ObjectId(session['current_note_objectID'])},
            {"$set": {
                "lines": json.loads(request.args.get('lines')),
                "current_line": request.args.get('current_line'),
                "maximum_line":  request.args.get('maximum_line'),
                "title": request.args.get('title'),
                "tags": tags}})
        return jsonp_succeed()

    if session['current_note_objectID'] == None and 'title' in request.args and request.args.get('title') != "":
        session['current_note_objectID'] = str(db.notes.insert_one({
            "lines": json.loads(request.args.get('lines')),
            "current_line": request.args.get('current_line'),
            "maximum_line":  request.args.get('maximum_line'),
            "title": request.args.get('title')
        }).inserted_id)
        db.users.update_one({"_id": ObjectId(session['userID'])},
                {"$push":{ "noteIDs": ObjectId(session['current_note_objectID']) }})
        return jsonify({"objectID":session['current_note_objectID']})

    return jsonp_failed()

@app.route('/notes/delete')
def notes_delete():
    if request_invalid():
        return jsonp_failed()
    if session['write_lock']:
        return jsonp_failed()

    if session['current_note_objectID'] == None:
        return jsonp_failed()

    lines = db.notes.find_one({"_id":ObjectId(session['current_note_objectID'])})
    if 'tags' in lines:
        delete_note_tags(lines['tags'])
    db.users.update_one({"_id": ObjectId(session['userID'])},
            {"$pull":{ "noteIDs": ObjectId(session['current_note_objectID']) }})
    db.notes.delete_one({"_id":ObjectId(session['current_note_objectID'])});
    session['current_note_objectID'] = None
    return jsonp_succeed()

# Haha! It's not secret at all...
app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'
app.run(threaded=True, host="0.0.0.0", debug=True, port=8080)
