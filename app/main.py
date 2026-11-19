import logging
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.cards import error_card, preview_card, summary_card
from app.config import settings
from app.security import validate_public_http_url, verify_chat_request
from app.services.extractor import fetch_article
from app.services.summarizer import summarize_article

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkmind")

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "linkmind-google-chat"}


@app.post("/chat/events")
async def chat_events(request: Request):
    await verify_chat_request(request)
    event = await request.json()
    event_type = event.get("type")
    logger.info("Received Google Chat event type=%s", event_type)

    if event_type == "MESSAGE":
        message = event.get("message") or {}
        matched_url = (message.get("matchedUrl") or {}).get("url")
        if not matched_url:
            return JSONResponse({})

        try:
            safe_url = validate_public_http_url(matched_url)
        except ValueError:
            return JSONResponse({"text": "LinkMind cannot preview this URL because it is not a supported public HTTP(S) link."})

        # In local development, optionally restrict previews to test domains.
        # In production, Google Chat's registered URL patterns are the primary allowlist.
        allowed_hosts = {h.strip().lower() for h in settings.allowed_test_hosts.split(",") if h.strip()}
        host = urlsplit(safe_url).hostname or ""
        if settings.chat_auth_mode == "disabled" and allowed_hosts and host not in allowed_hosts:
            return JSONResponse({"text": f"Local test mode: {host} is not in ALLOWED_TEST_HOSTS."})

        return JSONResponse(preview_card(safe_url))

    if event_type == "CARD_CLICKED":
        action = event.get("action") or {}
        if action.get("actionMethodName") != "summarize":
            return JSONResponse({})

        parameters = {p.get("key"): p.get("value") for p in action.get("parameters", [])}
        message = event.get("message") or {}
        raw_url = parameters.get("url") or (message.get("matchedUrl") or {}).get("url")
        sender_type = (message.get("sender") or {}).get("type", "HUMAN")
        if not raw_url:
            return JSONResponse(error_card("The original URL was not included in this action.", sender_type))

        try:
            safe_url = validate_public_http_url(raw_url)
            article = await fetch_article(safe_url)
            summary = await summarize_article(article["title"], article["url"], article["text"])
            return JSONResponse(summary_card(article["url"], article["title"], summary, sender_type))
        except Exception as exc:
            logger.exception("Summarization failed")
            # Avoid exposing internal exception details to Chat users.
            return JSONResponse(error_card(
                "We couldn't summarize this page. It may require sign-in, block automated access, "
                "contain unsupported content, or be temporarily unavailable. Please try another public article.",
                sender_type,
            ))

    # Google Chat may send ADDED_TO_SPACE, REMOVED_FROM_SPACE, etc.
    return JSONResponse({})
