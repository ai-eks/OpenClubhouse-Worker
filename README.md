# Clubhouse-Worker

A simple worker for [OpenClubhouse](https://github.com/ai-eks/OpenClubhouse) to sync data.

## Run

1. Install python packages by `pip install -r requirements.txt`
2. Change the configs in `config.template.py`.
3. Rename `config.template.py` to `config.py`.
4. Run `python main.py`.

## Third-part Software

- Python3.8
- requests
- requests_openapi
- pymongo
- mongoDB

## Reference

- <https://github.com/zhuowei/ClubhouseAPI>
  - Regex pattern: replace "(/(.+):\n    (post|get):\n)" with "$1      operationId: $2\n"

## Todo

- [x] large channel write
- [ ] update strategy
  - [ ] token update
  - [x] user count update
  - [x] channel status update
