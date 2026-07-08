import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class AdminUserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class AdminUser(AbstractBaseUser, PermissionsMixin):
    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = AdminUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "django_admin_users"


class AppUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    role = models.CharField(max_length=50, default="user")
    credits_balance = models.IntegerField(default=1_000_000_000)
    onboarding_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        return self.email


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(AppUser, on_delete=models.DO_NOTHING, db_column="user_id")
    type = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=50)
    logs = models.TextField()
    deployment_url = models.CharField(max_length=512, null=True, blank=True)
    deploy_subdomain = models.CharField(max_length=63, null=True, blank=True)
    git_history = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "projects"
        verbose_name = "Проект"
        verbose_name_plural = "Проекты"

    def __str__(self) -> str:
        return self.name


class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.DO_NOTHING, db_column="project_id")
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "chats"
        verbose_name = "Чат"
        verbose_name_plural = "Чаты"

    def __str__(self) -> str:
        return self.title


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(Chat, on_delete=models.DO_NOTHING, db_column="chat_id")
    role = models.CharField(max_length=32)
    content_markdown = models.TextField()
    metadata_json = models.TextField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "messages"
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"


class Deployment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.DO_NOTHING, db_column="project_id")
    status = models.CharField(max_length=32)
    image_ref = models.CharField(max_length=512, null=True, blank=True)
    container_id = models.CharField(max_length=255, null=True, blank=True)
    logs_ref = models.CharField(max_length=512, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "deployments"
        verbose_name = "Деплой"
        verbose_name_plural = "Деплои"


class Secret(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.DO_NOTHING, db_column="project_id")
    key = models.CharField(max_length=255)
    encrypted_value = models.TextField()
    kms_key_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "secrets"
        verbose_name = "Секрет"
        verbose_name_plural = "Секреты"


class RefreshToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(AppUser, on_delete=models.DO_NOTHING, db_column="user_id")
    token_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "refresh_tokens"
        verbose_name = "Refresh-токен"
        verbose_name_plural = "Refresh-токены"


class ChatFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.DO_NOTHING, db_column="project_id")
    chat = models.ForeignKey(Chat, on_delete=models.DO_NOTHING, db_column="chat_id")
    message = models.ForeignKey(
        Message, on_delete=models.DO_NOTHING, db_column="message_id", null=True, blank=True
    )
    user = models.ForeignKey(AppUser, on_delete=models.DO_NOTHING, db_column="user_id")
    object_key = models.CharField(max_length=1024)
    original_filename = models.CharField(max_length=512)
    content_type = models.CharField(max_length=255)
    size_bytes = models.IntegerField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "chat_files"
        verbose_name = "Файл чата"
        verbose_name_plural = "Файлы чата"


class DomainAppUser(AppUser):
    class Meta:
        proxy = True
        app_label = "domain"
        verbose_name = "Пользователь платформы"
        verbose_name_plural = "Пользователи платформы"


class DomainProject(Project):
    class Meta:
        proxy = True
        app_label = "domain"
        verbose_name = "Проект"
        verbose_name_plural = "Проекты"


class DomainSecret(Secret):
    class Meta:
        proxy = True
        app_label = "domain"
        verbose_name = "Секрет"
        verbose_name_plural = "Секреты"


class DomainDeployment(Deployment):
    class Meta:
        proxy = True
        app_label = "domain"
        verbose_name = "Деплой"
        verbose_name_plural = "Деплои"


class ChatSectionChat(Chat):
    class Meta:
        proxy = True
        app_label = "chats_section"
        verbose_name = "Чат"
        verbose_name_plural = "Чаты"


class ChatSectionFile(ChatFile):
    class Meta:
        proxy = True
        app_label = "chats_section"
        verbose_name = "Файл чата"
        verbose_name_plural = "Файлы чата"


class ChatSectionMessage(Message):
    class Meta:
        proxy = True
        app_label = "chats_section"
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"


class SystemAdminUser(AdminUser):
    class Meta:
        proxy = True
        app_label = "auth"
        verbose_name = "Системный пользователь"
        verbose_name_plural = "Системные пользователи"


class SystemSetting(models.Model):
    SETTING_TYPES = [
        ("api_key", "API ключ"),
        ("limit", "Лимит"),
        ("feature_toggle", "Фича-тогл"),
        ("periodic_task", "Периодическая задача"),
        ("other", "Прочее"),
    ]

    id = models.BigAutoField(primary_key=True)
    key = models.CharField(max_length=120, unique=True)
    title = models.CharField(max_length=255)
    setting_type = models.CharField(max_length=32, choices=SETTING_TYPES, default="other")
    value_text = models.TextField(blank=True, default="")
    value_json = models.JSONField(blank=True, null=True)
    value_number = models.IntegerField(blank=True, null=True)
    is_enabled = models.BooleanField(default=True)
    cron_expression = models.CharField(max_length=120, blank=True, default="")
    description = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "admin_system_settings"
        verbose_name = "Системная настройка"
        verbose_name_plural = "Системные настройки"

    def __str__(self) -> str:
        return self.title
