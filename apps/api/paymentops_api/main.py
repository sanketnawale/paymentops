"""ASGI entrypoint: uvicorn paymentops_api.main:app --host 0.0.0.0 --port 8000"""

from paymentops_api.app.factory import create_app

app = create_app()
