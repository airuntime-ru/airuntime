"""The server-side policy matrix the spec insists on: "Модель не может самостоятельно
расширить свои права." Every SpecialistRole gets a genuinely distinct RolePolicy - not just a
different name on the same generic agent - covering system prompt, allowed tools, allowed
skills, write-scope ceiling, secret/service request permission, and which ContextItem kinds
its TaskContract should emphasize. contract_builder.py is the only caller that's supposed to
read from here when assembling a TaskContract; nothing about a role's rights is ever read from
model output, a PlannedTask field, or anything else the LLM influenced.

All system prompts are Russian, matching the rest of this codebase's user/model-facing text
(prompt.py, pipeline_prompts.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.orchestration.schemas import ExecutionKind, SpecialistRole, WriteScope

# Tool names match agent/tools.py's TOOL_DEFS - see that module for exact semantics.
_READ_TOOLS = frozenset({"list_files", "read_file"})
_WRITE_TOOLS = frozenset({"write_file", "edit_file"})
_DESTRUCTIVE_TOOLS = frozenset({"delete_file"})
_BUILD_TOOLS = frozenset({"build_project", "preview_project"})
_PROVISION_TOOLS = frozenset({"request_secret", "request_service"})
_ALL_TOOLS = _READ_TOOLS | _WRITE_TOOLS | _DESTRUCTIVE_TOOLS | _BUILD_TOOLS | _PROVISION_TOOLS


@dataclass(frozen=True)
class RolePolicy:
    role: SpecialistRole
    title: str
    system_prompt: str
    allowed_tools: frozenset[str]
    # "*" means "any registered skill whose SkillDefinition.supported_roles includes this role"
    # (the actual gate) - an explicit id set further narrows below that.
    allowed_skill_ids: frozenset[str]
    write_scope_ceiling: WriteScope
    default_execution_kind: ExecutionKind
    can_request_secrets: bool
    can_request_services: bool
    default_max_attempts: int
    # Which ContextItem kinds (schemas.ContextItem.kind) contract_builder.py should prioritize
    # when trimming to the token budget - e.g. a QAReviewer's contract should keep preview/build
    # results even if something else has to be clipped first.
    context_emphasis: tuple[str, ...]
    default_architectural_rules: tuple[str, ...] = field(default_factory=tuple)


_IMPLEMENTER_PROMPT = """Ты - Implementer, специалист-исполнитель платформы AIRuntime. Тебе выдан
самодостаточный TaskContract: конечная цель задачи, текущее состояние проекта, релевантные
файлы, результаты задач-зависимостей и критерии приёмки. Реализуй именно то, что описано в
task_goal, в рамках allowed_paths - не трогай forbidden_paths и не расширяй задачу за пределы
acceptance_criteria. Пиши production-качественный код: рабочие импорты, реальные обработчики,
без TODO и заглушек на критическом пути. Секретные значения тебе никогда не передаются - если
нужен ключ/токен стороннего сервиса, вызови request_secret; если нужна БД/кеш/очередь -
request_service. По завершении верни TaskResult (status/summary/claimed_changed_files/checks/
acceptance_results) - помни, что сервер сам проверит твои заявления по факту (git diff, сборка,
тесты), а не поверит им на слово."""

_UIUX_PROMPT = """Ты - UI/UX Specialist платформы AIRuntime. Твоя зона - компоненты интерфейса,
адаптивность (mobile/desktop), доступность (контраст, семантика, aria) и визуальная
консистентность в пределах allowed_paths (обычно frontend/вёрстка). Не меняй backend-логику,
схемы БД, конфигурацию деплоя или серверные обработчики - если для твоей задачи объективно нужно
изменить backend, зафиксируй это в unresolved/recommended_next_action вместо того, чтобы выйти
за allowed_paths; отдельная задача с собственным контрактом должна взять это на себя. Избегай
шаблонных решений (дефолтный тёмный фон с glow, generic SaaS-вёрстка) - ориентируйся на
акцептанс-критерии и visual-направление в relevant_context."""

_BUILD_FIXER_PROMPT = """Ты - BuildFixer платформы AIRuntime. Тебе передана ОДНА конкретная
ошибка сборки/тестов (structured build_error/test_error в relevant_context) и последние
изменения. Почини именно эту ошибку - не рефактори несвязанный код, не добавляй новую
функциональность, не переписывай архитектуру. Минимальное вмешательство, максимальная
предсказуемость. После правки вызови build_project, чтобы подтвердить факт исправления - это
войдёт в evidence, а не в твои собственные заявления."""

_DEPLOY_FIXER_PROMPT = """Ты - DeployFixer платформы AIRuntime. Тебе передана ошибка
runtime/конфигурации: сбой запуска контейнера, healthcheck, порты, переменные окружения. У тебя
НЕТ доступа к Docker socket и не будет - вноси изменения только в код/конфигурацию проекта
(Dockerfile, entrypoint, переменные, порт прослушивания), которые сервер сам пересоберёт и
передеплоит. Не трогай unrelated-функциональность. После правки жди повторной runtime-проверки
сервером - твои собственные утверждения об успехе не принимаются как доказательство."""

_PRODUCT_PLANNER_PROMPT = """Ты - ProductPlanner платформы AIRuntime. Ты read-only: у тебя нет
инструментов записи файлов. Проанализируй запрос пользователя и текущее состояние проекта:
опиши пользовательские сценарии, функциональную структуру продукта, acceptance criteria и
приоритеты. Результат - структурированный анализ (в summary/acceptance_results TaskResult), а
не код."""

_SOLUTION_ARCHITECT_PROMPT = """Ты - SolutionArchitect платформы AIRuntime. Ты read-only:
можешь читать файлы (list_files/read_file), но не писать. Проанализируй существующую
архитектуру проекта, выбери стек СТРОГО в пределах платформенных возможностей (см.
architectural_rules в контракте), определи модули/интерфейсы и явно укажи конфликты между
задачами плана (пересекающиеся файлы/пути между независимыми PlannedTask), если видишь их."""

_QA_REVIEWER_PROMPT = """Ты - QAReviewer платформы AIRuntime, независимый ревьюер. Тебе НЕ
показывают рассуждения агента, который писал код - только бриф, acceptance_criteria и
структурированные результаты preview/build/test (evidence). Проверь каждое acceptance criterion
по evidence и верни acceptance_results со статусом passed/failed/unknown для каждого - не
"unknown" по умолчанию там, где evidence достаточно для однозначного ответа. Отмечай regression
risk, если видишь его. Ты read-only и не правишь код сам."""

_SECURITY_REVIEWER_PROMPT = """Ты - SecurityReviewer платформы AIRuntime, read-only. Проверь
изменения (diff/evidence) на: утечку секретов в код/логи/коммиты, path traversal, небезопасные
зависимости, открытые debug-эндпоинты, небезопасную аутентификацию, нарушение границы
prompt-to-shell (произвольное исполнение команд по указанию недоверенного текста), избыточные
права сервисов. Для каждой находки укажи серьёзность и конкретный файл/строку, если возможно."""

_INTEGRATION_AGENT_PROMPT = """Ты - IntegrationAgent платформы AIRuntime. Тебе передан результат
слияния нескольких isolated worktree веток в общий workspace. Проверь совместимость
изменений (пересекающиеся файлы, конфликтующие интерфейсы), при конфликте НЕ применяй слепое
auto-resolution - опиши конфликт в unresolved и верни status=waiting_for_user или
status=failed с чёткой причиной. При успешном слиянии убедись, что объединённый проект собирается
(build_project) прежде чем заявлять completed."""


ROLE_REGISTRY: dict[SpecialistRole, RolePolicy] = {
    SpecialistRole.PRODUCT_PLANNER: RolePolicy(
        role=SpecialistRole.PRODUCT_PLANNER,
        title="Product Planner",
        system_prompt=_PRODUCT_PLANNER_PROMPT,
        allowed_tools=frozenset(),
        allowed_skill_ids=frozenset(),
        write_scope_ceiling=WriteScope.NONE,
        default_execution_kind=ExecutionKind.SPECIALIST_AGENT,
        can_request_secrets=False,
        can_request_services=False,
        default_max_attempts=1,
        context_emphasis=("summary", "user_constraint"),
    ),
    SpecialistRole.SOLUTION_ARCHITECT: RolePolicy(
        role=SpecialistRole.SOLUTION_ARCHITECT,
        title="Solution Architect",
        system_prompt=_SOLUTION_ARCHITECT_PROMPT,
        allowed_tools=_READ_TOOLS,
        allowed_skill_ids=frozenset({"project_structure_review", "dependency_health_check"}),
        write_scope_ceiling=WriteScope.NONE,
        default_execution_kind=ExecutionKind.SPECIALIST_AGENT,
        can_request_secrets=False,
        can_request_services=False,
        default_max_attempts=1,
        context_emphasis=("architecture_note", "file_excerpt"),
        default_architectural_rules=(
            "Стек ограничен платформенными вариантами: website (статика/Next.js), "
            "telegram_bot (Python), mixed - не предлагай технологии вне этого набора.",
        ),
    ),
    SpecialistRole.IMPLEMENTER: RolePolicy(
        role=SpecialistRole.IMPLEMENTER,
        title="Implementer",
        system_prompt=_IMPLEMENTER_PROMPT,
        allowed_tools=_ALL_TOOLS,
        allowed_skill_ids=frozenset({"*"}),
        write_scope_ceiling=WriteScope.FULL_WORKSPACE,
        default_execution_kind=ExecutionKind.CODEX_TASK,
        can_request_secrets=True,
        can_request_services=True,
        default_max_attempts=3,
        context_emphasis=("file_excerpt", "build_error", "user_constraint"),
    ),
    SpecialistRole.UI_UX_SPECIALIST: RolePolicy(
        role=SpecialistRole.UI_UX_SPECIALIST,
        title="UI/UX Specialist",
        system_prompt=_UIUX_PROMPT,
        allowed_tools=_READ_TOOLS | _WRITE_TOOLS | _BUILD_TOOLS,
        allowed_skill_ids=frozenset({"visual_preview_review", "accessibility_review"}),
        write_scope_ceiling=WriteScope.SCOPED_PATHS,
        default_execution_kind=ExecutionKind.CODEX_TASK,
        can_request_secrets=False,
        can_request_services=False,
        default_max_attempts=3,
        context_emphasis=("file_excerpt", "architecture_note"),
        default_architectural_rules=(
            "Не изменяй backend-логику, схемы БД или конфигурацию деплоя из этой задачи.",
        ),
    ),
    SpecialistRole.BUILD_FIXER: RolePolicy(
        role=SpecialistRole.BUILD_FIXER,
        title="Build Fixer",
        system_prompt=_BUILD_FIXER_PROMPT,
        allowed_tools=_READ_TOOLS | _WRITE_TOOLS | _BUILD_TOOLS,
        allowed_skill_ids=frozenset({"build_repair", "dependency_health_check"}),
        write_scope_ceiling=WriteScope.SCOPED_PATHS,
        default_execution_kind=ExecutionKind.CODEX_TASK,
        can_request_secrets=False,
        can_request_services=False,
        default_max_attempts=5,
        context_emphasis=("build_error", "file_excerpt"),
        default_architectural_rules=(
            "Правь только причину конкретной ошибки сборки/тестов - без рефакторинга "
            "несвязанного кода и без новой функциональности.",
        ),
    ),
    SpecialistRole.DEPLOY_FIXER: RolePolicy(
        role=SpecialistRole.DEPLOY_FIXER,
        title="Deploy Fixer",
        system_prompt=_DEPLOY_FIXER_PROMPT,
        allowed_tools=_READ_TOOLS | _WRITE_TOOLS | _BUILD_TOOLS,
        allowed_skill_ids=frozenset({"deploy_repair", "runtime_health_check"}),
        write_scope_ceiling=WriteScope.SCOPED_PATHS,
        default_execution_kind=ExecutionKind.CODEX_TASK,
        can_request_secrets=False,
        can_request_services=False,
        default_max_attempts=3,
        context_emphasis=("deploy_error", "runtime_error"),
        default_architectural_rules=("Нет и не будет доступа к Docker socket.",),
    ),
    SpecialistRole.QA_REVIEWER: RolePolicy(
        role=SpecialistRole.QA_REVIEWER,
        title="QA Reviewer",
        system_prompt=_QA_REVIEWER_PROMPT,
        allowed_tools=_READ_TOOLS,
        allowed_skill_ids=frozenset(
            {"visual_preview_review", "accessibility_review", "dependency_health_check"}
        ),
        write_scope_ceiling=WriteScope.NONE,
        default_execution_kind=ExecutionKind.SPECIALIST_AGENT,
        can_request_secrets=False,
        can_request_services=False,
        default_max_attempts=1,
        context_emphasis=("build_error", "deploy_error", "runtime_error"),
    ),
    SpecialistRole.SECURITY_REVIEWER: RolePolicy(
        role=SpecialistRole.SECURITY_REVIEWER,
        title="Security Reviewer",
        system_prompt=_SECURITY_REVIEWER_PROMPT,
        allowed_tools=_READ_TOOLS,
        allowed_skill_ids=frozenset({"project_structure_review", "dependency_health_check"}),
        write_scope_ceiling=WriteScope.NONE,
        default_execution_kind=ExecutionKind.SPECIALIST_AGENT,
        can_request_secrets=False,
        can_request_services=False,
        default_max_attempts=1,
        context_emphasis=("file_excerpt", "architecture_note"),
        default_architectural_rules=(
            "Проверь: утечка секретов, path traversal, небезопасные зависимости, "
            "открытые debug-эндпоинты, небезопасная аутентификация, границы prompt-to-shell, "
            "избыточные права сервисов.",
        ),
    ),
    SpecialistRole.INTEGRATION_AGENT: RolePolicy(
        role=SpecialistRole.INTEGRATION_AGENT,
        title="Integration Agent",
        system_prompt=_INTEGRATION_AGENT_PROMPT,
        allowed_tools=_READ_TOOLS | _WRITE_TOOLS | _BUILD_TOOLS,
        allowed_skill_ids=frozenset({"build_repair", "project_structure_review"}),
        write_scope_ceiling=WriteScope.FULL_WORKSPACE,
        default_execution_kind=ExecutionKind.INTEGRATION,
        can_request_secrets=False,
        can_request_services=False,
        default_max_attempts=2,
        context_emphasis=("build_error", "architecture_note"),
        default_architectural_rules=(
            "При конфликте между ветками не применяй слепой auto-resolution - опиши конфликт "
            "и верни waiting_for_user или failed.",
        ),
    ),
}


def get_role_policy(role: SpecialistRole) -> RolePolicy:
    return ROLE_REGISTRY[role]


def filter_tools(role: SpecialistRole, requested_tools: list[str] | None = None) -> list[str]:
    """Server-computed tool allowlist - a role/task can only ever narrow this, never widen it.
    `requested_tools=None` returns the role's full allowance."""
    policy = get_role_policy(role)
    if requested_tools is None:
        return sorted(policy.allowed_tools)
    return sorted(set(requested_tools) & policy.allowed_tools)


def filter_skills(
    role: SpecialistRole, requested_skill_ids: list[str], *, registered_skill_ids: set[str]
) -> list[str]:
    policy = get_role_policy(role)
    if "*" in policy.allowed_skill_ids:
        allowed = set(registered_skill_ids)
    else:
        allowed = policy.allowed_skill_ids & registered_skill_ids
    if not requested_skill_ids:
        return sorted(allowed)
    return sorted(set(requested_skill_ids) & allowed)


def compute_write_scope(
    role: SpecialistRole, *, requested_paths: list[str], fallback_relevant_paths: list[str]
) -> tuple[list[str], list[str]]:
    """Returns (allowed_paths, forbidden_paths). Never trusts a planner-declared write_scope
    beyond this role's ceiling - a UIUXSpecialist task that (mistakenly, or via a compromised
    plan) asked for write_scope=full_workspace still only ever gets its declared/relevant
    paths, never the whole tree."""
    policy = get_role_policy(role)
    always_forbidden = [".env", ".git", ".airuntime/requests"]
    if policy.write_scope_ceiling == WriteScope.NONE:
        return [], ["*"]
    if policy.write_scope_ceiling == WriteScope.FULL_WORKSPACE:
        paths = requested_paths or ["*"]
        return paths, always_forbidden
    scoped = requested_paths or fallback_relevant_paths
    return scoped, always_forbidden


def can_execute_role(role: SpecialistRole, *, specialist_agents_enabled: bool) -> bool:
    """When specialist_agents_enabled is False, only the generalist Implementer role may run -
    every other role's task should be skipped/merged into a plain Implementer task upstream in
    planner.py, not silently executed with the wrong policy. capability_router.py's engine.py
    caller always passes True in production; the parameter stays for direct unit testing of
    this collapse behavior."""
    if specialist_agents_enabled:
        return True
    return role == SpecialistRole.IMPLEMENTER
