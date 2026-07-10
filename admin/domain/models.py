from core.models import AppUser, CreditTopUp, Deployment, ModerationEvent, Plan, Project, Secret


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


class BlockedProject(Project):
    class Meta:
        proxy = True
        verbose_name = "Заблокированный проект"
        verbose_name_plural = "Заблокированные проекты"


class DomainModerationEvent(ModerationEvent):
    class Meta:
        proxy = True
        verbose_name = "Событие модерации"
        verbose_name_plural = "История модерации"


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


class DomainPlan(Plan):
    class Meta:
        proxy = True
        verbose_name = "Тариф"
        verbose_name_plural = "Тарифы"


class DomainCreditTopUp(CreditTopUp):
    class Meta:
        proxy = True
        verbose_name = "Пополнение баланса"
        verbose_name_plural = "Пополнения баланса"
