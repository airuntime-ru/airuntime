from src.services.email_templates import LOGO_CID, login_code_email, password_reset_email, verify_email


def test_login_code_email_contains_branding():
    content = login_code_email(code="482913", minutes=10)
    assert content.subject == "Код входа в AIRuntime"
    assert "482913" in content.plain
    assert f"cid:{LOGO_CID}" in content.html
    assert "AIRUNTIME" in content.html
    assert "Вход в AIRuntime" in content.html
    assert "10 минут" in content.html


def test_verify_email_template():
    content = verify_email(verify_url="https://airuntime.ru/auth/verify?token=abc")
    assert "Подтвердите почту" in content.subject
    assert "https://airuntime.ru/auth/verify?token=abc" in content.plain
    assert "Подтвердить почту" in content.html
    assert f"cid:{LOGO_CID}" in content.html


def test_password_reset_template():
    content = password_reset_email(reset_url="https://airuntime.ru/auth/reset?token=xyz")
    assert "Сброс пароля" in content.subject
    assert "Сбросить пароль" in content.html
    assert f"cid:{LOGO_CID}" in content.html
