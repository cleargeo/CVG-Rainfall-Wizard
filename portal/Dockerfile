# =============================================================================
# CVG Rainfall Wizard — Portal Container
# Clearview Geographic LLC — Proprietary and Confidential
# =============================================================================
FROM python:3.11-slim

LABEL org.opencontainers.image.title="CVG Rainfall Wizard Portal"
LABEL org.opencontainers.image.vendor="Clearview Geographic LLC"
LABEL org.opencontainers.image.licenses="Proprietary"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV RFW_API_URL=http://rainfall-wizard:8020
ENV PORT=8040

EXPOSE 8040

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8040"]
