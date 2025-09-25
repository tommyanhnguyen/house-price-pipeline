FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy code + artifacts (pipeline sẽ tạo artifacts trước khi build)
COPY . .

EXPOSE 8501

# Add healthcheck (every 30s, fail if 3 retries fail)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost:8501/ || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

