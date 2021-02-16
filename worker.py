from pymongo import MongoClient
# from pymongo.objectid import ObjectId

from ch_helper import ClubHouseHelper
import queue
import time
import random
import json


class Worker():
    def __init__(self, clubHouseHelper: ClubHouseHelper, mongo_uri: str, max_retries: int = 5, token_file: str = None):
        self.max_retries = 5
        self.client = MongoClient(mongo_uri)
        self.db = self.client.clubhouse
        self.chh = clubHouseHelper
        self.channels = set()
        self.queue = queue.Queue()
        self.token_id = None
        self.token_file = token_file

        if self.token_file is not None:
            print("GetTokenFromJsonFile")
            self.getTokenFromJsonFile(self.token_file)
        else:
            print("getTokenFromDB")
            self.getTokenFromDB()
        self.getAllAliveChannelsFromDB()

    def login(self):
        print("Try to login...")
        res = self.chh.start_auth()
        # res = {'success': True}
        if res['success'] is True:
            verification_code = input('Input verification_code: ')
            res = self.chh.login(verification_code)
            if res['success'] is True:
                self.chh.setSecret(
                    res['user_profile']['user_id'], res["auth_token"])
                if self.token_file is not None:
                    self.saveToken2JsonFile(self.token_file, res)
                else:
                    self.saveToken2DB(res)
                print("Login Success!")
                return
        print(res)
        raise Exception("Failed to login.")

    def getTokenFromDB(self):
        token = self.db.tokens.find_one({'is_alive': True})
        if token:
            self.chh.setSecret(
                token['user_profile']['user_id'], token["auth_token"])
            self.token_id = token['_id']
        else:
            self.login()

    def getTokenFromJsonFile(self, file: str):
        try:
            with open(file, 'r') as fp:
                token = json.load(fp)
                self.chh.setSecret(
                    token['user_profile']['user_id'], token["auth_token"])
        except Exception as e:
            print("Failed to load token", repr(e))
            self.login()

    def saveToken2JsonFile(self, file: str, token: dict):
        with open(file, 'w') as fp:
            json.dump(token, fp)

    def saveToken2DB(self, token):
        if self.token_id is not None:
            self.db.tokens.update_one(
                {"_id": self.token_id},
                {"$set": {"is_alive": False}}
            )
        token['is_alive'] = True
        cursor = self.db.tokens.insert_one(token)
        if cursor:
            self.token_id = cursor.inserted_id

    def endChannel(self, channel_uid):
        channel_id, channel_str = channel_uid
        self.db.channels.update_one(
            {"_id": channel_id}, {"$set": {'success': False}})
        self.channels.remove(channel_uid)
        print(f"Channel{channel_uid} is end.")

    def checkChannelStatus(self, channel_uid: tuple, pushintoqueue=True):
        try:
            channel_id, channel_str = channel_uid
            isEnd = self.chh.checkChannelIsEnd(channel_str)
            if isEnd:
                self.endChannel(channel_uid)
                print(f"Room {channel_uid} is ended!")
            elif pushintoqueue:
                self.pushJoinedChannel(channel_uid)
            return isEnd
        except Exception as e:
            print(f"Cannot check channel {channel_uid} status.", repr(e))
            return False

    def joinChannel(self, channel_uid: tuple):
        if not self.checkChannelStatus(channel_uid, pushintoqueue=False):
            channel_id, channel_str = channel_uid
            # attempts = self.max_retries
            # while attempts > 0:
            try:
                res = self.chh.joinChannel(channel_str)
                if res['success'] is True:
                    self.db.channels.update_one(
                        {"_id": channel_id},
                        {"$set": {
                            "success": res['success'],
                            "is_empty": res['is_empty'],
                            "token": res['token'],
                            "rtm_token": res['rtm_token'],
                            "pubnub_token": res['pubnub_token'],
                            "pubnub_origin": res['pubnub_origin'],
                            "pubnub_heartbeat_value": res['pubnub_heartbeat_value'],
                            "pubnub_heartbeat_interval": res['pubnub_heartbeat_interval'],
                            "pubnub_enable": res['pubnub_enable'],
                            "agora_native_mute": res['agora_native_mute'],
                            "users": res['users'],
                            "joined": True
                        }}
                    )
                    self.pushJoinedChannel(channel_uid)
                elif "That room is no longer available" in res['error_message']:
                    self.endChannel(channel_uid)
                else:
                    print(
                        f"Error: Failed to join Channel[{channel_uid}-{channel_uid}], reason:{res} ")
            except Exception as e:
                print(
                    f"Cannot join channel {channel_uid}.", repr(e))
                self.pushUnjoinedChannel(channel_uid)

    def insertChannel(self, channel: dict):
        # channel["_id"] = channel['channel_id']
        channel['reviewed'] = False
        channel['_id'] = channel['channel_id']
        channel['success'] = True
        channel['joined'] = False
        self.db.channels.insert_one(channel)

    def getChannels(self, retry_times=0):
        if retry_times < self.max_retries:
            try:
                res = self.chh.getChannels()
                for channel in res['channels']:
                    channel_uid = (channel['channel_id'], channel['channel'])
                    if channel_uid not in self.channels:
                        self.addChannel(channel)
                        self.pushChannel(channel)
                        self.insertChannel(channel)
                self.pushGetChannels()
                return True
            except Exception as e:
                if 401 <= int(e.args[0]) <= 403:
                    self.login()
                    return self.getChannels(retry_times+1)
                else:
                    raise Exception(f"Failed to get channels", repr(e))
        raise Exception(f"Maximum attempts for getChannels")

    def pushUnjoinedChannel(self, channel_uid: tuple):
        self.queue.put((self.joinChannel, channel_uid))

    def pushJoinedChannel(self, channel_uid: tuple):
        self.queue.put((self.checkChannelStatus, channel_uid))

    def pushGetChannels(self):
        self.queue.put((self.getChannels, 0))

    def pushChannel(self, channel: dict):
        channel_uid = (channel['channel_id'], channel['channel'])
        if "token" not in channel:
            self.pushUnjoinedChannel(channel_uid)
        else:
            self.pushJoinedChannel(channel_uid)

    def addChannel(self, channel: dict):
        self.channels.add((channel['channel_id'], channel['channel']))

    def getAllAliveChannelsFromDB(self):
        cursor = self.db.channels.find({"success": True})
        self.pushGetChannels()
        for channel in cursor:
            self.addChannel(channel)
            self.pushChannel(channel)

    def autoRun(self):
        while not self.queue.empty():
            func, para = self.queue.get()
            print(f"Call {func} with {para}")
            func(para)
            wait_time = random.randint(5, 10)
            if func == self.checkChannelStatus:
                wait_time = 1
            print(f"Sleep {wait_time}s")
            time.sleep(wait_time)
