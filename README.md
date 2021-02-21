# OpenClubhouse-Worker

This is a simple worker for [OpenClubhouse](https://github.com/ai-eks/OpenClubhouse) to sync CH channel data.

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
  - Regex pattern for requests_openapi: replace "(/(.+):\n    (post|get):\n)" with "$1      operationId: $2\n"
- <https://github.com/lafin/clubhouseapi>

## Todo

- [x] large channel write
  - reduce the number of saved users
- [ ] update strategy
  - [ ] token update (low priority) - maybe add a probability to join again
  - [x] user count update
  - [x] channel status update
- [ ] Exception notification

## Running in Docker
```
docker build -t ochw .
```
