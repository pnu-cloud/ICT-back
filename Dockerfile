FROM python:3.12.4

WORKDIR /app

COPY ./requirements.txt /app/

RUN pip install -r requirements.txt

COPY ./app /app

CMD ["flask", "run", "--host=0.0.0.0"]
