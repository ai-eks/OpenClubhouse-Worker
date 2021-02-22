import uuid
import requests_openapi
import requests


class ClubHouseHelper():
    def __init__(self, phone: str, url: str = "./api.yaml", device_id: str = None):
        self.client = requests_openapi.Client()
        self.client.load_spec_from_file(url)
        self.phone = phone
        self.base_headers = {
            "User-Agent": "clubhouse/269 (iPhone; iOS 14.1; Scale/3.00)",
            "Content-Type": "application/json; charset=utf-8",
            "CH-Languages": "en-US",
            "CH-Locale": "en_US",
            "CH-AppVersion": "0.1.15",
            "CH-AppBuild": "269",
            "CH-DeviceId": device_id or str(uuid.uuid1()),
        }
        self.headers = {k: v for k, v in self.base_headers.items()}

    def start_auth(self):
        data = {"phone_number": self.phone}
        res = self.client.start_phone_number_auth(
            json=data, headers=self.headers)
        if res.status_code == 200:
            return res.json()
        raise Exception(res.status_code, res.reason, res.url, res.headers)

    def login(self, verification_code: str):
        data = {"phone_number": self.phone,
                "verification_code": verification_code}
        res = self.client.complete_phone_number_auth(
            json=data, headers=self.headers)
        if res.status_code == 200:
            return res.json()
        raise Exception(res.status_code, res.reason, res.url, res.headers)

    def setSecret(self, user_id: int, auth_token: str):
        self.headers['Authorization'] = f"Token {auth_token}"
        self.headers['CH-UserID'] = str(int(user_id))

    def getChannels(self):
        res = self.client.get_channels(headers=self.headers)
        if res.status_code == 200:
            return res.json()
        raise Exception(res.status_code, res.reason, res.url, res.headers)

    def joinChannel(self, channel):
        data = {"channel": channel}
        res = self.client.join_channel(json=data, headers=self.headers)
        if res.status_code == 200:
            return res.json()
        raise Exception(res.status_code, res.reason, res.url, res.headers)

    def checkChannelIsEnd(self, channel: str):
        url = f"https://www.joinclubhouse.com/room/{channel}"
        response = requests.get(url)
        if "This room has already ended" in response.text:
            return True
        return False


if __name__ == "__main__":
    from config import mongo_uri, device_id, api_uri, phone
    chh = ClubHouseHelper(phone=phone, url=api_uri, device_id=device_id)

