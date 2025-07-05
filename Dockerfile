FROM python:3.12
LABEL authors="adam-kwiatkowski"

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./api /code/api
COPY ./bot /code/bot

RUN python -c "from bot.bosko_bot import main; main()"
