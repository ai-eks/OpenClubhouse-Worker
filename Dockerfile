FROM python:3.8

COPY requirements.txt /app/
WORKDIR /app
RUN ls ./requirements.txt
RUN pip install -r requirements.txt
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY src/ ./

CMD [ "python", "./main.py" ]
