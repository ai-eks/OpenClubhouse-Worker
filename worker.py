from pymongo import MongoClient
# from pymongo.objectid import ObjectId

from ch_helper import ClubHouseHelper
import queue
import time
import random
import json


class Worker():
    def __init__(
            self,
            clubHouseHelper: ClubHouseHelper,
            mongo_uri: str,
            token_file: str = None,
            fresh_interval: int = 3600,
            max_retries: int = 5,
            user_limit: int = 500):
        """
        Params:
        - clubHouseHelper: ClubHouseHelper obj.
        - mongo_uri: full mongoDB connect uri.
        - token_file: token json file. If it is None, load token from DB.
        - fresh_time: the timeing to update channel user counts. Unit is second
        - max_retries: maximum retry attempts for some action. 
        """
        self.client = MongoClient(mongo_uri)
        self.db = self.client.clubhouse
        self.chh = clubHouseHelper
        self.channels = set()
        self.check_queue = queue.Queue()
        self.join_queue = queue.Queue()
        self.token_id = None
        self.token_file = token_file
        self.last_fresh_time = 0
        self.fresh_interval = fresh_interval
        self.max_retries = max_retries
        self.user_limit = user_limit

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

    def getChannels(self, retry_times=0):
        "Query all channels from CH"
        if retry_times < self.max_retries:
            try:
                res = self.chh.getChannels()
                fresh = False
                if time.time() - self.last_fresh_time > self.fresh_interval:
                    fresh = True
                    self.last_fresh_time = time.time()
                for channel in res['channels']:
                    channel_uid = (channel['channel_id'], channel['channel'])
                    if channel_uid not in self.channels:
                        print(f"Find a new Channel {channel_uid}")
                        self.addChannel2Set(channel)
                        self.pushChannel2Queue(channel)
                        self.insertChannel2DB(channel)
                    elif fresh:
                        print(f"Update a old Channel {channel_uid}")
                        self.updateChannelInfo2DB(channel)
                    else:
                        print(f"Skip a old Channel {channel_uid}")
                return True
            except Exception as e:
                if 401 <= int(e.args[0]) <= 403:
                    self.login()
                    return self.getChannels(retry_times+1)
                else:
                    raise Exception(f"Failed to get channels", repr(e))
        raise Exception(f"Maximum attempts for getChannels")

    def joinChannel(self, channel_uid: tuple):
        "Get token and all users of a specific channel"

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
                            "users": res['users'][:self.user_limit],
                            "joined": True
                        }}
                    )
                    self.pushJoinedChannel2Queue(channel_uid)
                elif "That room is no longer available" in res['error_message']:
                    self.endChannel(channel_uid)
                else:
                    print(
                        f"Error: Failed to join Channel[{channel_uid}-{channel_uid}], reason:{res} ")
            except Exception as e:
                print(
                    f"Cannot join channel {channel_uid}.", repr(e))
                self.pushUnjoinedChannel2Queue(channel_uid)

    def checkChannelStatus(self, channel_uid: tuple, pushintoqueue=True):
        "Check if a channel is end"
        try:
            channel_id, channel_str = channel_uid
            isEnd = self.chh.checkChannelIsEnd(channel_str)
            if isEnd:
                self.endChannel(channel_uid)
                print(f"Room {channel_uid} is ended!")
            elif pushintoqueue:
                self.pushJoinedChannel2Queue(channel_uid)
            return isEnd
        except Exception as e:
            print(f"Cannot check channel {channel_uid} status.", repr(e))
            return False

    def endChannel(self, channel_uid):
        "Mark a channel end"
        try:
            channel_id, channel_str = channel_uid
            self.db.channels.update_one(
                {"_id": channel_id}, {"$set": {'success': False}})
            self.channels.remove(channel_uid)
            print(f"Channel{channel_uid} is end.")
        except Exception as e:
            print(f"Cannot end channel {channel_uid} status.", repr(e))

    def getAllAliveChannelsFromDB(self):
        cursor = self.db.channels.find({"success": True})
        for channel in cursor:
            self.addChannel2Set(channel)
            self.pushChannel2Queue(channel)

    def insertChannel2DB(self, channel: dict):
        channel['reviewed'] = False
        channel['_id'] = channel['channel_id']
        channel['success'] = True
        channel['joined'] = False
        self.db.channels.insert_one(channel)

    def updateChannelInfo2DB(self, channel: dict):
        self.db.channels.update_one(
            {"_id": channel['channel_id']},
            {"$set": {
                "num_speakers": channel['num_speakers'],
                "num_all": channel['num_all'],
            }})

    def pushUnjoinedChannel2Queue(self, channel_uid: tuple):
        self.join_queue.put(channel_uid)

    def pushJoinedChannel2Queue(self, channel_uid: tuple):
        self.check_queue.put(channel_uid)

    def pushChannel2Queue(self, channel: dict):
        channel_uid = (channel['channel_id'], channel['channel'])
        if "token" not in channel:
            self.pushUnjoinedChannel2Queue(channel_uid)
        else:
            self.pushJoinedChannel2Queue(channel_uid)

    def addChannel2Set(self, channel: dict):
        self.channels.add((channel['channel_id'], channel['channel']))

    def wait(self, left: int, right: int):
        wait_time = random.randint(left, right)
        print(f"Sleep {wait_time}s")
        time.sleep(wait_time)

    def autoRun(self):
        while True:
            print(f"Call getChannels()")
            self.getChannels()
            while not self.join_queue.empty():
                channel_uid = self.join_queue.get()
                print(f"Call joinChannel({channel_uid})")
                self.joinChannel(channel_uid)
                self.wait(5, 20)
            while not self.check_queue.empty():
                channel_uid = self.check_queue.get()
                print(f"Call checkChannelStatus({channel_uid})")
                self.checkChannelStatus(channel_uid, True)
                self.wait(5, 10)
