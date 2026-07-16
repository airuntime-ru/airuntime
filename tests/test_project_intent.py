from src.services.project_intent import infer_project_type


def test_infer_project_type_website_only():
    assert infer_project_type("Хочу лендинг для кофейни") == "website"


def test_infer_project_type_bot_only():
    assert infer_project_type("Нужен Telegram-бот для поддержки клиентов") == "telegram_bot"


def test_infer_project_type_mixed_when_both_mentioned():
    assert (
        infer_project_type("Хочу сайт для студии и Telegram-бота, который принимает заявки")
        == "mixed"
    )


def test_infer_project_type_defaults_to_website_on_no_signal():
    assert infer_project_type("Сделай что-нибудь классное") == "website"
