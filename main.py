from flask import Flask, request
from flask_jsonpify import jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import json

app = Flask('tagged')
client = MongoClient()
db = client['tagged']

current_tag_objectID = None
current_note_objectID = None

@app.route('/admin/clear')
def admin_clear():
    global current_note_objectID
    db.notes.drop()
    current_note_objectID = None
    return ""
    
@app.route('/notes/all')
def notes_all():
    global current_note_objectID
    def get_note_des(note):
        des_str = ""
        for line in note['lines']:
            if line['type'] != "h1":
                for char in line['raw']:
                    des_str += char
                    if len(des_str) >= 200:
                        return des_str
        return des_str

    items = []
    notes = db.notes.find()
    for note in notes:
        item = {}
        item['title'] = note['title']
        item['des'] = get_note_des(note)
        item['objectID'] = str(note['_id'])
        items.append(item)
    return jsonify({"items":items, "current_objectID":str(current_note_objectID)})

@app.route('/notes/create')
def notes_create():
    global current_note_objectID
    new_note = [{"type":"", "text":"", "raw":""}]
    current_line = 0
    maximum_line = 0
    current_note_objectID = None
    return jsonify({"lines":new_note, "current_line":current_line, "maximum_line":maximum_line})

@app.route('/notes/open')
def notes_open():
    global current_note_objectID
    current_note_objectID = ObjectId(request.args.get('objectID'))
    lines = db.notes.find_one({"_id":current_note_objectID})
    return jsonify({
        "lines": lines['lines'],
        "current_line": lines['current_line'],
        "maximum_line": lines['maximum_line'],
        "title": lines['title']
    })

@app.route('/notes/recover')
def notes_recover():
    global current_note_objectID
    if current_note_objectID == None:
        return notes_create()
    else:
        lines = db.notes.find_one({"_id":current_note_objectID})
        return jsonify({
            "lines": lines['lines'],
            "current_line": lines['current_line'],
            "maximum_line": lines['maximum_line'],
            "title": lines['title'],
            "objectID": str(lines['_id'])
        })


@app.route('/notes/save')
def notes_save():
    global current_note_objectID
    if current_note_objectID != None:
        db.notes.update_one(
            {"_id": current_note_objectID},
            {"$set": {
                "lines": json.loads(request.args.get('lines')),
                "current_line": request.args.get('current_line'),
                "maximum_line":  request.args.get('maximum_line'),
                "title": request.args.get('title')}
            })
        return ""

    if current_note_objectID == None and request.args.get('title') != "":
        current_note_objectID = db.notes.insert_one({
            "lines": json.loads(request.args.get('lines')),
            "current_line": request.args.get('current_line'),
            "maximum_line":  request.args.get('maximum_line'),
            "title": request.args.get('title')
        }).inserted_id
        return jsonify({"subjectID":str(current_note_objectID)})

    return ""

app.run(debug=True, port=8080)
