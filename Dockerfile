FROM python:3.12
LABEL authors="adam-kwiatkowski"

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./api /app/api
COPY ./bot /app/bot

CMD ["python", "-c", "from bot.bosko_bot import main; main()"]