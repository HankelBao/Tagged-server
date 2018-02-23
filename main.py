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

@app.route('/admin/clear')
def admin_clear():
    """ Clear Function for admin
    
    This Function will set the system to initial state.

    There are no args or returns

    """
    global current_note_objectID
    db.notes.drop()
    db.tags.drop()
    current_note_objectID = None
    return ""

@app.route('/tags/all')
def tags_all():
    """ Return all tags available

    Requet Args:
        None

    Return:
        items (array) : An array containing all the available info including "name" and "objectID"

    """
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
    """ Open a Tag

    Request Args:
        objectID (str): 
            The objectID of the tag you want to select. The objectID could be abtained from tags_all request
            When the objectID is nothing(""), it means no tags are chosen.

    Return:
        status (str): Whether succeed or not

    """
    global current_tag_objectID
    objectID_str = request.args.get('objectID')
    if objectID_str == "":
        current_tag_objectID = None
    else:
        current_tag_objectID = ObjectId(objectID_str)

    return jsonify({"status":"succeed"})

@app.route('/notes/all')
def notes_all():
    """ Showing All the notes of the Tag you selected
        
    Request Args:
        None

    Return:
        items (array): An array containing all the info of the notes overview
           .title (str): The title of one of the article
           .des (str): The first 200 words of the article, excluded the title.
           .objectID (str): The objectID of the article
        tag_name (str): The name of the selected tag. It will be 'Notes' when no tags are selected
        current_objectID (str): The objectID of the note object selected
        
    """
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

    if current_tag_objectID:
        notes = []
        tag = db.tags.find_one({"_id": current_tag_objectID})
        for noteID in tag['noteID']:
            note = db.notes.find_one({"_id": noteID})
            notes.append(note)
    else:
        notes = db.notes.find()

    items = []
    for note in notes:
        item = {}
        item['title'] = note['title']
        item['des'] = get_note_des(note)
        item['objectID'] = str(note['_id'])
        items.append(item)

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
    """ Create a note
    
    Request Args:
        None

    Return:
        An empty Line Object

    """
    global current_note_objectID
    new_note = [{"type":"", "text":"", "raw":""}]
    current_line = 0
    maximum_line = 0
    current_note_objectID = None
    return jsonify({"lines":new_note, "current_line":current_line, "maximum_line":maximum_line})

@app.route('/notes/open')
def notes_open():
    global current_note_objectID
    global write_lock
    write_lock = True
    current_note_objectID = ObjectId(request.args.get('objectID'))
    lines = db.notes.find_one({"_id":current_note_objectID})
    if 'tags' in lines:
        tags = lines['tags']
    else:
        tags = None
    return jsonify({
        "lines": lines['lines'],
        "current_line": lines['current_line'],
        "maximum_line": lines['maximum_line'],
        "title": lines['title'],
        "tags": tags
    })

@app.route('/notes/unlock')
def write_unlock():
    global write_lock
    write_lock = False
    return jsonify({"status":"succeed"})

@app.route('/notes/delete')
def notes_delete():
    global current_note_objectID
    if current_note_objectID == None:
        return ""
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
        return jsonify({"status":"succeed"})

@app.route('/notes/recover')
def notes_recover():
    global current_note_objectID
    if current_note_objectID == None:
        return notes_create()
    else:
        lines = db.notes.find_one({"_id":current_note_objectID})
        if 'tags' in lines:
            tags = lines['tags']
        else:
            tags = None
        return jsonify({
            "lines": lines['lines'],
            "current_line": lines['current_line'],
            "maximum_line": lines['maximum_line'],
            "title": lines['title'],
            "objectID": str(lines['_id']),
            "tags": tags
        })


@app.route('/notes/save')
def notes_save():
    global current_note_objectID
    global write_lock
    if write_lock:
        return jsonify({"status":"failed"})
    
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
        return jsonify({"status":"succeed"})

    if current_note_objectID == None and request.args.get('title') != "":
        current_note_objectID = db.notes.insert_one({
            "lines": json.loads(request.args.get('lines')),
            "current_line": request.args.get('current_line'),
            "maximum_line":  request.args.get('maximum_line'),
            "title": request.args.get('title')
        }).inserted_id
        return jsonify({"subjectID":str(current_note_objectID)})

    return ""

app.run(threaded=True, host="0.0.0.0", debug=True, port=8080)
