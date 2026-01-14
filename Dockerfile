FROM python:3.9-slim
WORKDIR /app

ENV PIP_ROOT_USER_ACTION=ignore

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app", "--timeout", "120"]