from core.models import AppUser, Deployment, Project, Secret


class DomainAppUser(AppUser):
    class Meta:
        proxy = True
        verbose_name = "Пользователь платформы"
        verbose_name_plural = "Пользователи платформы"


class DomainProject(Project):
    class Meta:
        proxy = True
        verbose_name = "Проект"
        verbose_name_plural = "Проекты"


class DomainSecret(Secret):
    class Meta:
        proxy = True
        verbose_name = "Секрет"
        verbose_name_plural = "Секреты"


class DomainDeployment(Deployment):
    class Meta:
        proxy = True
        verbose_name = "Деплой"
        verbose_name_plural = "Деплои"
