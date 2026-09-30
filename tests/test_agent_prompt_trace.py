from __future__ import annotations

from contextlib import contextmanager

from app import agent as agent_module
from app import mock_llm, mock_rag


class ManagedPrompt:
    version = 3

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class RecordingLangfuseClient:
    def __init__(self) -> None:
        self.prompt = ManagedPrompt()
        self.span_updates: list[dict] = []

    def get_prompt(self, name: str, **kwargs):
        return self.prompt

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)


class RecordingChildObservationClient:
    def __init__(self) -> None:
        self.span_updates: list[dict] = []
        self.generation_updates: list[dict] = []

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)

    def update_current_generation(self, **kwargs) -> None:
        self.generation_updates.append(kwargs)


def test_agent_records_prompt_version_with_v4_observation_api(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    monkeypatch.setenv("LANGFUSE_PROMPT_LABEL", "production")
    client = RecordingLangfuseClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    propagated: list[dict] = []

    @contextmanager
    def record_attributes(**kwargs):
        propagated.append(kwargs)
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    agent = agent_module.LabAgent()
    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message="Explain traces",
        correlation_id="req-12345678",
    )

    span_update = client.span_updates[-1]
    assert span_update["metadata"] == {
        "doc_count": 1,
        "query_preview": "Explain traces",
        "prompt_name": "day13-chat",
        "prompt_label": "production",
        "prompt_version": "3",
        "prompt_source": "langfuse",
        "prompt_fetch_error": "",
    }
    assert span_update["version"] == "3"
    assert propagated[0]["metadata"]["correlation_id"] == "req-12345678"
    assert propagated[-1]["prompt"] is client.prompt


def test_retrieval_observation_records_only_safe_metadata(monkeypatch) -> None:
    client = RecordingChildObservationClient()
    monkeypatch.setattr(mock_rag, "get_langfuse_client", lambda: client)

    documents = mock_rag.retrieve.__wrapped__(
        "Contact student@vinuni.edu.vn about monitoring",
        correlation_id="req-12345678",
        feature="qa",
    )

    assert documents
    assert client.span_updates[-1]["metadata"] == {
        "correlation_id": "req-12345678",
        "docs_found": 1,
        "feature": "qa",
    }
    assert "student@vinuni.edu.vn" not in str(client.span_updates)


def test_generation_observation_records_usage_cost_and_managed_prompt(monkeypatch) -> None:
    client = RecordingChildObservationClient()
    managed_prompt = ManagedPrompt()
    monkeypatch.setattr(mock_llm, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(mock_llm.random, "randint", lambda *_: 100)
    monkeypatch.setattr(mock_llm.time, "sleep", lambda *_: None)

    llm = mock_llm.FakeLLM(model="fake-llm-v1")
    response = mock_llm.FakeLLM.generate.__wrapped__(
        llm,
        "compiled prompt with student@vinuni.edu.vn",
        correlation_id="req-12345678",
        prompt_name="day13-chat",
        prompt_label="production",
        prompt_version="3",
        prompt_object=managed_prompt,
    )

    update = client.generation_updates[-1]
    assert update["model"] == "fake-llm-v1"
    assert update["usage_details"] == {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    assert update["cost_details"]["total"] > 0
    assert update["metadata"] == {
        "correlation_id": "req-12345678",
        "prompt_name": "day13-chat",
        "prompt_label": "production",
        "prompt_version": "3",
    }
    assert update["prompt"] is managed_prompt
    assert "student@vinuni.edu.vn" not in str(update)
