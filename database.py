"""
database.py
This module contains the database link and name
It also allows teh user to interact with database
"""
from pymongo import MongoClient, ASCENDING

#Database commented out for privacy reasons
MONGO_URI = ""
DB_NAME = "projectdb"
client = MongoClient(MONGO_URI)
db     = client[DB_NAME]
coll   = db["lecturers"]

coll.create_index([("profileUrl", ASCENDING)], unique=True)
coll.create_index([("name", ASCENDING)])  

def get_lecturers_collection():
    """
    Returns the MongoDB collection for lecturers.
    """
    return coll
