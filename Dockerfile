FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE BRAND_ASSET_LICENSE.md THIRD_PARTY_NOTICES.md ./
COPY src ./src
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

COPY app.py ./
COPY app_pages ./app_pages
COPY .streamlit ./.streamlit

USER pwuser

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableXsrfProtection=true", "--server.enableCORS=true", "--server.maxUploadSize=10", "--client.showErrorDetails=none"]
