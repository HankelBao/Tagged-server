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
from flask import Flask, request
from flask_jsonpify import jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import time
import json

app = Flask('tagged')
client = MongoClient()
db = client['tagged']

current_tag_objectID = None
current_note_objectID = None
write_lock = False

def jsonp_succeed():
    return jsonify({"status":"succeed"})

def jsonp_failed():
    return jsonify({"status":"failed"})

@app.route('/notes/unlock')
def write_unlock():
    global write_lock
    write_lock = False
    return jsonp_succeed()

@app.route('/tags/all')
def tags_all():
    global current_tag_objectID
    items = []
    tags = db.tags.find()
    for tag in tags:
        item = {}
        item['name'] = tag['name']
        item['objectID'] = str(tag['_id'])
        items.append(item)

    return jsonify({"items":items})

@app.route('/tags/open')
def tags_open():
    global current_tag_objectID
    objectID_str = request.args.get('objectID')
    if objectID_str == "":
        current_tag_objectID = None
    else:
        current_tag_objectID = ObjectId(objectID_str)

    return jsonp_succeed()

@app.route('/notes/all')
def notes_all():
    global current_tag_objectID
    global current_note_objectID
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

    # notes
    if current_tag_objectID:
        notes = []
        tag = db.tags.find_one({"_id": current_tag_objectID})
        for noteID in tag['noteID']:
            note = db.notes.find_one({"_id": noteID})
            notes.append(note)
    else:
        notes = db.notes.find()

    # items 
    items = []
    for note in notes:
        item = {}
        item['title'] = note['title']
        item['des'] = get_note_des(note)
        item['objectID'] = str(note['_id'])
        items.append(item)

    # tag_name 
    if current_tag_objectID == None:
        tag_name = "Notes"
    else:
        tag = db.tags.find_one({"_id": current_tag_objectID})
        tag_name = "#" + tag['name']

    if current_note_objectID == None:
        return jsonify({"items":items, "tag_name":tag_name})
    else:
        return jsonify({"items":items, "tag_name":tag_name, "current_objectID":str(current_note_objectID)})

@app.route('/notes/create')
def notes_create():
    global current_note_objectID
    current_note_objectID = None
    write_lock = True
    return jsonp_succeed()

@app.route('/notes/open')
def notes_open():
    global current_note_objectID
    global write_lock
    write_lock = True
    current_note_objectID = ObjectId(request.args.get('objectID'))
    return jsonp_succeed()

@app.route('/notes/load')
def notes_load():
    global current_note_objectID
    if current_note_objectID == None:
        return jsonify({
            "lines":[{"type":"", "text":"", "raw":""}],
            "current_line":0,
            "maximum_line":0,
            "tags":""
        })
    else:
        lines = db.notes.find_one({"_id":current_note_objectID})
        return jsonify({
            "lines": lines['lines'],
            "current_line": lines['current_line'],
            "maximum_line": lines['maximum_line'],
            "title": lines['title'],
            "tags": lines['tags'] if 'tags' in lines else ""
        })



@app.route('/notes/save')
def notes_save():
    global current_note_objectID
    global write_lock
    if write_lock:
        return jsonp_failed()
    
    if current_note_objectID != None:
        if request.args.get('tags') == "null":
            tags = []
        else:
            tags = json.loads(request.args.get('tags'))

        lines = db.notes.find_one({"_id":current_note_objectID})

        if 'tags' in lines:
            delete_tags = list(set(lines['tags']) - set(tags))
        else:
            delete_tags = []

        for delete_tag in delete_tags:
            tag = db.tags.find_one({"name": delete_tag})
            tag['noteID'].remove(current_note_objectID)
            if len(tag['noteID']) == 0:
                db.tags.delete_one({"name": delete_tag})
            else:
                db.tags.update_one({"name": delete_tag}, {"$set": tag})

        if 'tags' in lines:
            create_tags = list(set(tags) - set(lines['tags']))
        else:
            create_tags = tags

        for create_tag in create_tags:
            if db.tags.find_one({"name":create_tag}):
                db.tags.update_one({"name":create_tag},
                        {"$push":{"noteID":current_note_objectID}})
            else:
                tag = {}
                tag['name'] = create_tag
                tag['noteID'] = [current_note_objectID]
                db.tags.insert_one(tag)

        db.notes.update_one(
            {"_id": current_note_objectID},
            {"$set": {
                "lines": json.loads(request.args.get('lines')),
                "current_line": request.args.get('current_line'),
                "maximum_line":  request.args.get('maximum_line'),
                "title": request.args.get('title'),
                "tags": tags}})
        return jsonp_succeed()

    if current_note_objectID == None and 'title' in request.args and request.args.get('title') != "":
        current_note_objectID = db.notes.insert_one({
            "lines": json.loads(request.args.get('lines')),
            "current_line": request.args.get('current_line'),
            "maximum_line":  request.args.get('maximum_line'),
            "title": request.args.get('title')
        }).inserted_id
        return jsonify({"objectID":str(current_note_objectID)})

    return jsonp_failed()

@app.route('/notes/delete')
def notes_delete():
    global current_note_objectID
    if current_note_objectID == None:
        return jsonp_failed()
    else:
        lines = db.notes.find_one({"_id":current_note_objectID})
        if 'tags' in lines:
            for tag_name in lines['tags']:
                tag = db.tags.find_one({"name": tag_name})
                tag['noteID'].remove(current_note_objectID)
                if len(tag['noteID']) == 0:
                    db.tags.delete_one({"name": tag_name})
                else:
                    db.tags.update_one({"name": tag_name}, {"$set": tag})
        db.notes.delete_one({"_id":current_note_objectID});
        current_note_objectID = None
        return jsonp_succeed()

app.run(threaded=True, host="0.0.0.0", debug=True, port=8080)
