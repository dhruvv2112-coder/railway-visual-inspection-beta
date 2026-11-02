# OHE Visual AI Patrol server: FastAPI inspection service + reviewer web (/ohe/review) + trained detector.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY shared /srv/shared
COPY backend /srv/backend
# rapidocr pulls the GUI build of OpenCV; swap it for the headless build (no X11 libraries on a server)
RUN pip install "/srv/backend[ocr]" \
 && pip uninstall -y opencv-python \
 && pip install --force-reinstall --no-deps "opencv-python-headless>=4.10" \
 && python -c "import cv2, rapidocr_onnxruntime, onnxruntime; print('cv2', cv2.__version__)" \
 && mkdir -p /srv/models /data
# Trained detector (ohe_detector.onnx + ohe_detector.names.json); placed in deploy/models by CI or by hand.
COPY deploy/models/ /srv/models/
WORKDIR /srv/backend
ENV RVI_MODEL_DIR=/srv/models RVI_DATABASE_URL=sqlite:////data/rvi.db RVI_EVIDENCE_DIR=/data/evidence \
    RVI_USERS_FILE=/data/users.yaml RVI_AUTH_MODE=token
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
