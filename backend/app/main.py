from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.middleware.rate_limit import rateLimitMiddleware
from app.core.middleware.logging import loggingMiddleware
from app.api import auth

app = FastAPI(title="Trustworthy TA Agent")

app.middleware("http")(rateLimitMiddleware)
app.middleware("http")(loggingMiddleware)

app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)