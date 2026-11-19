from urllib.parse import urlsplit


def _safe_text(value: str, limit: int = 2500) -> str:
    return (value or "").replace("<", "&lt;").replace(">", "&gt;")[:limit]


def preview_card(url: str) -> dict:
    host = urlsplit(url).netloc
    return {
        "actionResponse": {"type": "UPDATE_USER_MESSAGE_CARDS"},
        "cardsV2": [{
            "cardId": "linkmind-preview",
            "card": {
                "header": {
                    "title": "LinkMind AI Summary",
                    "subtitle": f"Quickly understand links from {host}",
                },
                "sections": [{
                    "widgets": [
                        {"textParagraph": {"text": "Get the main ideas and key takeaway without reading the entire article."}},
                        {"buttonList": {"buttons": [{
                            "text": "✨ Summarize article",
                            "onClick": {"action": {
                                "function": "summarize",
                                "parameters": [{"key": "url", "value": url}],
                            }},
                        }]}}
                    ]
                }],
            },
        }],
    }


def summary_card(url: str, title: str, summary: str, sender_type: str = "HUMAN") -> dict:
    action_type = "UPDATE_USER_MESSAGE_CARDS" if sender_type == "HUMAN" else "UPDATE_MESSAGE"
    return {
        "actionResponse": {"type": action_type},
        "cardsV2": [{
            "cardId": "linkmind-preview",
            "card": {
                "header": {
                    "title": "LinkMind – Summary",
                    "subtitle": _safe_text(title, 180),
                },
                "sections": [{
                    "widgets": [
                        {"textParagraph": {"text": _safe_text(summary, 6000)}},
                        {"decoratedText": {
                            "topLabel": "Original article",
                            "text": _safe_text(url, 500),
                        }},
                        {"buttonList": {"buttons": [{
                            "text": "Open original article",
                            "onClick": {"openLink": {"url": url}},
                        }]}}
                    ]
                }],
            },
        }],
    }


def error_card(message: str, sender_type: str = "HUMAN") -> dict:
    action_type = "UPDATE_USER_MESSAGE_CARDS" if sender_type == "HUMAN" else "UPDATE_MESSAGE"
    return {
        "actionResponse": {"type": action_type},
        "cardsV2": [{
            "cardId": "linkmind-preview",
            "card": {
                "header": {"title": "LinkMind could not summarize this link"},
                "sections": [{"widgets": [{"textParagraph": {"text": _safe_text(message, 1000)}}]}],
            },
        }],
    }
