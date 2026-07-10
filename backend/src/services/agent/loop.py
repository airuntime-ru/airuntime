"""The coding agent's turn loop: think out loud, call tools, repeat.

This is what replaces the old "one JSON blob wipes the whole project" flow.
On every user message the agent can look at the files that already exist,
read the ones relevant to the request, and make targeted edits - the same
loop shape used by tool-using coding assistants (read -> edit -> verify).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.services.agent.events import AgentDone, TextDelta, ToolCallRequested, ToolCallResult
from src.services.agent.providers import get_agent_provider
from src.services.agent.tools import TOOL_DEFS, WorkspaceTools

MAX_ITERATIONS = 14


@dataclass
class AgentRunResult:
    final_text: str
    touched_files: set[str]
    iterations: int
    stopped_reason: str
    error: str | None = None


def _normalize_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Collapse consecutive same-role turns and drop a leading assistant turn.

    Some providers (Anthropic in particular) require strictly alternating
    user/assistant turns starting with "user". Chat history read back from
    the database should already alternate, but we normalize defensively so a
    stray duplicate role never breaks the wire format.
    """

    normalized: list[dict[str, str]] = []
    for item in history:
        role = "assistant" if item.get("role") == "assistant" else "user"
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if normalized and normalized[-1]["role"] == role:
            normalized[-1]["content"] += f"\n\n{content}"
        else:
            normalized.append({"role": role, "content": content})
    if normalized and normalized[0]["role"] == "assistant":
        normalized = normalized[1:]
    return normalized


class CodingAgentSession:
    def __init__(
        self,
        *,
        provider_name: str,
        model: str,
        api_key: str,
        workspace: WorkspaceTools,
        system_prompt: str,
    ) -> None:
        self.provider_name = provider_name
        self.provider = get_agent_provider(provider_name)
        self.model = model
        self.api_key = api_key
        self.workspace = workspace
        self.system_prompt = system_prompt

    async def run(
        self, *, history: list[dict[str, str]], user_message: str
    ) -> AsyncIterator[TextDelta | ToolCallRequested | ToolCallResult | AgentDone]:
        tools = TOOL_DEFS if self.provider.supports_tools() else []
        wire_messages = self.provider.build_messages(_normalize_history(history), user_message)

        final_text_parts: list[str] = []
        iterations = 0

        while iterations < MAX_ITERATIONS:
            iterations += 1
            turn_final = None
            async for event in self.provider.stream_turn(
                system_prompt=self.system_prompt,
                messages=wire_messages,
                tools=tools,
                model=self.model,
                api_key=self.api_key,
            ):
                if isinstance(event, TextDelta):
                    if event.text:
                        final_text_parts.append(event.text)
                        yield event
                else:
                    turn_final = event

            if turn_final is None:
                yield AgentDone(reason="error", error="Provider stream ended without a result")
                return

            if turn_final.stop_reason == "error":
                yield AgentDone(reason="error", error=turn_final.error or "Unknown provider error")
                return

            if turn_final.wire_message is not None:
                wire_messages.append(turn_final.wire_message)

            if not turn_final.tool_calls:
                yield AgentDone(reason="stop")
                return

            results: list[ToolCallResult] = []
            for call in turn_final.tool_calls:
                yield call
                outcome = self.workspace.call(call.name, call.arguments)
                result = ToolCallResult(
                    call_id=call.call_id,
                    name=call.name,
                    ok=outcome.ok,
                    summary=outcome.summary,
                    content=outcome.content,
                )
                results.append(result)
                yield result

            wire_messages.extend(self.provider.build_tool_result_messages(results))

        yield AgentDone(reason="max_iterations")
