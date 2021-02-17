import requests_openapi
from config import mongo_uri, device_uuid, api_uri, phone, token_file, fresh_interval, user_limit
from worker import Worker
from ch_helper import ClubHouseHelper


def test(worker: Worker = None):
    if worker is None:
        chh = ClubHouseHelper(phone=phone, url=api_uri, uuid=device_uuid)
        worker = Worker(clubHouseHelper=chh, mongo_uri=mongo_uri)
    # worker.getTokenFromDB()
    print("token_id:", worker.token_id)
    print("headers:", worker.chh.headers)
    print(len(worker.channels), "channels:", worker.channels)
    print("Join queue len:", len(worker.join_queue))
    print("Check queue len:", len(worker.check_queue))
    return worker
    # worker.getChannels()
    # print("token_id:", worker.token_id)
    # print(worker.token_id, worker.chh.headers)
    # worker.getAllAliveChannelsFromDB()


def main():
    chh = ClubHouseHelper(phone=phone, url=api_uri, uuid=device_uuid)
    worker = Worker(
        clubHouseHelper=chh,
        mongo_uri=mongo_uri,
        token_file=token_file,
        fresh_interval=fresh_interval,
        user_limit=user_limit)
    test(worker)
    worker.autoRun()


if __name__ == "__main__":
    main()
    # test()
