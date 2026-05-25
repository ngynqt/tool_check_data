FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Set working directory
WORKDIR /app

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Copy requirements file
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ /app/src/
COPY .env /app/
COPY .env.example /app/

# Create logs directory
RUN mkdir -p /app/logs /app/browser_session

# Expose port
EXPOSE 8080

# Run FastAPI application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
