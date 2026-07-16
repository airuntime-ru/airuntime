from types import SimpleNamespace

from src.services.project_intent import infer_project_type, update_project_type_from_prompt


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


def test_infer_project_type_webhook_is_bot_not_mixed():
    # "webhook" contains "web" as a prefix — must not count as a site signal.
    assert infer_project_type("Сделай telegram bot на webhook") == "telegram_bot"


def test_update_project_type_ignores_prompt_without_signals():
    project = SimpleNamespace(type="telegram_bot", deploy_subdomain="keep-me")
    assert update_project_type_from_prompt(project, "Ок, продолжай") is False
    assert project.type == "telegram_bot"
    assert project.deploy_subdomain == "keep-me"


def test_reconcile_website_typed_bot_without_site(tmp_path):
    from src.services.project_intent import reconcile_type_with_workspace

    (tmp_path / "app.py").write_text("print('bot')", encoding="utf-8")
    project = SimpleNamespace(type="website", deploy_subdomain="bot-site")
    assert reconcile_type_with_workspace(project, tmp_path) is True
    assert project.type == "telegram_bot"
    assert project.deploy_subdomain is None


def test_reconcile_website_with_bot_secret_without_site(tmp_path):
    from src.services.project_intent import reconcile_type_with_workspace

    project = SimpleNamespace(type="website", deploy_subdomain="bot-site")
    assert reconcile_type_with_workspace(project, tmp_path, has_bot_secret=True) is True
    assert project.type == "telegram_bot"
    assert project.deploy_subdomain is None


def test_reconcile_keeps_mixed_with_only_bot_secret_before_files(tmp_path):
    from src.services.project_intent import reconcile_type_with_workspace

    project = SimpleNamespace(type="mixed", deploy_subdomain="studio")
    assert reconcile_type_with_workspace(project, tmp_path, has_bot_secret=True) is False
    assert project.type == "mixed"


def test_reconcile_mixed_without_website(tmp_path):
    from src.services.project_intent import reconcile_type_with_workspace

    (tmp_path / "app.py").write_text("print('bot')", encoding="utf-8")
    project = SimpleNamespace(type="mixed", deploy_subdomain="bot-site")
    assert reconcile_type_with_workspace(project, tmp_path) is True
    assert project.type == "telegram_bot"
    assert project.deploy_subdomain is None
