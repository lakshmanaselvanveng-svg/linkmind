from app.cards import preview_card, summary_card


def test_preview_card_contains_summarize_action():
    card = preview_card("https://example.com/article")
    button = card["cardsV2"][0]["card"]["sections"][0]["widgets"][1]["buttonList"]["buttons"][0]
    assert button["onClick"]["action"]["function"] == "summarize"
    assert button["onClick"]["action"]["parameters"][0]["value"] == "https://example.com/article"


def test_summary_card_updates_human_message_card():
    card = summary_card("https://example.com/a", "Title", "Summary", "HUMAN")
    assert card["actionResponse"]["type"] == "UPDATE_USER_MESSAGE_CARDS"
