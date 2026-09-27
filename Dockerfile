# RedFlag API image. Build: docker build -t redflag .   Run: docker run -p 8900:8900 -e GEMINI_API_KEY=... redflag
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DISABLE_SQLALCHEMY_CEXT_RUNTIME=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY redflag/ redflag/
COPY app/ app/
COPY evals/ evals/
COPY data/processed/ data/processed/
# Prospectus PDFs and the vector index are built at start-up if missing (public SEBI filings).
RUN useradd -m redflag && chown -R redflag /app
USER redflag
EXPOSE 8900
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8900/health')"
CMD ["sh", "-c", "python -m redflag.setup && uvicorn redflag.api:app --host 0.0.0.0 --port 8900"]
