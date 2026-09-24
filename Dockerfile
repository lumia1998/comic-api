FROM python:3.11-slim-trixie

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0t64 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# arm/v7 has no prebuilt wheels for pycryptodome/pillow/cffi: source builds need gcc
# and libffi-dev; Pillow also needs libjpeg/zlib headers or the resulting wheel
# silently lacks JPEG support.
ARG TARGETPLATFORM
RUN if [ "$TARGETPLATFORM" = "linux/arm/v7" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
        gcc python3-dev libffi-dev libjpeg62-turbo-dev zlib1g-dev \
      && rm -rf /var/lib/apt/lists/* ; \
    fi
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p src/web/static src/web/templates

EXPOSE 8699

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8699"]
