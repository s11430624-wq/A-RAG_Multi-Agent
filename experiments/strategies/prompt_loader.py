from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from experiments.strategies.models import (
    CapabilityContext,
    ModelVisibleTask,
    RenderedPrompt,
)

_TEMPLATE_NAMES = {
    "single_llm.txt",
    "planner.txt",
    "coder.txt",
    "reviewer.txt",
    "repair.txt",
}


def canonical_prompt_json(value: Any) -> str:
    normalized = _to_json_value(value)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


class PromptLoader:
    def __init__(self, template_root: Path | None = None) -> None:
        self.template_root = template_root or Path(__file__).resolve().parents[1] / "prompts"

    def template_path(self, name: str) -> Path:
        if name not in _TEMPLATE_NAMES:
            raise ValueError(f"unknown prompt template: {name}")
        return self.template_root / name

    def render(
        self,
        name: str,
        *,
        task: ModelVisibleTask,
        capability: CapabilityContext,
        data: Mapping[str, Any] | None = None,
        evidence: tuple[Any, ...] | None = None,
        retrieved_queries: tuple[Any, ...] | None = None,
        retrieval_required: bool | None = None,
        retrieval_progress_note: str | None = None,
    ) -> RenderedPrompt:
        raw = self.template_path(name).read_bytes()
        template_hash = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8")
        task_payload = {
            "expected_behavior": task.expected_behavior,
            "files_to_modify": task.files_to_modify,
            "forbidden_behaviors": task.forbidden_behaviors,
            "task_description": task.task_description,
            "task_id": task.task_id,
        }
        starter_payload = tuple(asdict(item) for item in task.starter_files)
        effective_retrieval_required = retrieval_required
        if effective_retrieval_required is None:
            effective_retrieval_required = not bool(retrieved_queries)
        if capability.retrieval_enabled:
            if name in ("planner.txt", "coder.txt"):
                if not effective_retrieval_required:
                    extra_guidance = ""
                    if name == "coder.txt":
                        extra_guidance = (
                            " Use the visible evidence and plan to generate the smallest valid patch. "
                            "Do not repeat retrieval unless specific required information is still missing."
                        )
                    capability_text = (
                        "<CAPABILITY>Retrieval is available only through exact JSON action=retrieve requests. You MUST query the retrieval corpus using this exact JSON tool format to perform a keyword_search: {\"action\": \"retrieve\", \"tool\": \"keyword_search\", \"query\": \"calculate_pass_rate\", \"top_k\": 1}. The top_k field MUST be an integer from 1 to 3 only; never use 4 or higher. You have already performed retrieval. If you have sufficient information, you may now provide your final output."
                        f"{extra_guidance}</CAPABILITY>"
                    )
                else:
                    capability_text = (
                        "<CAPABILITY>Retrieval is available only through exact JSON action=retrieve requests. You MUST query the retrieval corpus using this exact JSON tool format to perform a keyword_search: {\"action\": \"retrieve\", \"tool\": \"keyword_search\", \"query\": \"calculate_pass_rate\", \"top_k\": 1}. The top_k field MUST be an integer from 1 to 3 only; never use 4 or higher. You MUST perform retrieval using this format at least once before submitting your final output.</CAPABILITY>"
                    )
            else:
                capability_text = (
                    "<CAPABILITY>Retrieval is available only through exact JSON action=retrieve requests.</CAPABILITY>"
                )
        else:
            capability_text = "<CAPABILITY>Retrieval is unavailable. Do not request or claim evidence.</CAPABILITY>"
        evidence_text = ""
        if capability.retrieval_enabled:
            evidence_text = f"<EVIDENCE_DATA>{canonical_prompt_json(evidence or ())}</EVIDENCE_DATA>"
            if retrieved_queries:
                evidence_text += f"<RETRIEVED_QUERIES>{canonical_prompt_json(retrieved_queries)}</RETRIEVED_QUERIES>"
            if retrieval_progress_note:
                evidence_text += (
                    f"<RETRIEVAL_PROGRESS>{canonical_prompt_json({'note': retrieval_progress_note})}</RETRIEVAL_PROGRESS>"
                )
        replacements = {
            "{{TASK_DATA}}": canonical_prompt_json(task_payload),
            "{{STARTER_FILE_DATA}}": canonical_prompt_json(starter_payload),
            "{{ROLE_DATA}}": canonical_prompt_json(data or {}),
            "{{CAPABILITY_BLOCK}}": capability_text,
            "{{EVIDENCE_BLOCK}}": evidence_text,
        }
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, value)
        if re.search(r"\{\{[A-Z_]+\}\}", text):
            raise ValueError("prompt contains unresolved placeholder")
        rendered_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return RenderedPrompt(name, template_hash, text, rendered_hash)


def _to_json_value(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return [_to_json_value(item) for item in value]
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json_value(item) for key, item in value.items()}
    return value
