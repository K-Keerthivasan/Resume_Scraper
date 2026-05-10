FROM python:3.12-slim

WORKDIR /app

COPY Scraper.py ./

RUN mkdir -p /app/job_data

EXPOSE 8765

CMD ["python3", "Scraper.py", "serve", "0.0.0.0", "8765"]
