FROM python:3.12

WORKDIR /app

RUN pip install poetry==1.8.3

COPY pyproject.toml .

RUN poetry config virtualenvs.create false \
    && poetry install

COPY . /app/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]