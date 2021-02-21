import pymongo
from config import mongo_uri

client = pymongo.MongoClient(mongo_uri)
collection = client.clubhouse