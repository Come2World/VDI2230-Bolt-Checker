import json
from pathlib import Path
from typing import Any

from vdi2230.domain.models import ProjectSnapshot


SCHEMA_VERSION = 1
FORMAT_ID = "vdi2230-bolt-project"


def save_project(path: Path, project: ProjectSnapshot) -> None:
    document = {
        "format": FORMAT_ID,
        "schema_version": SCHEMA_VERSION,
        "case_id": project.case_id,
        "title": project.title,
        "inputs": project.inputs,
        "input_units": project.input_units,
        "input_sources": project.input_sources,
        "assumptions": list(project.assumptions),
        "metadata": project.metadata,
    }
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def load_project(path: Path) -> ProjectSnapshot:
    def reject_constant(constant: str) -> None:
        raise ValueError(f"Invalid non-finite JSON number: {constant}")

    document: Any = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_constant,
    )
    if not isinstance(document, dict):
        raise ValueError("Project file must contain a JSON object")
    if document.get("format") != FORMAT_ID:
        raise ValueError("Unrecognized project file format")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported project schema version: "
            f"{document.get('schema_version')!r}"
        )

    case_id = document.get("case_id")
    title = document.get("title")
    inputs = document.get("inputs")
    assumptions = document.get("assumptions")
    metadata = document.get("metadata")
    input_units = document.get("input_units", {})
    input_sources = document.get("input_sources", {})
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("Project case_id must be a non-empty string")
    if not isinstance(title, str):
        raise ValueError("Project title must be a string")
    if not isinstance(inputs, dict):
        raise ValueError("Project inputs must be a JSON object")
    if not isinstance(assumptions, list) or not all(
        isinstance(item, str) for item in assumptions
    ):
        raise ValueError("Project assumptions must be a list of strings")
    if not isinstance(metadata, dict):
        raise ValueError("Project metadata must be a JSON object")
    if not isinstance(input_units, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in input_units.items()
    ):
        raise ValueError("Project input_units must map strings to strings")
    if not isinstance(input_sources, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in input_sources.items()
    ):
        raise ValueError("Project input_sources must map strings to strings")
    _validate_json_numbers(inputs, "inputs")
    _validate_json_numbers(metadata, "metadata")

    return ProjectSnapshot(
        case_id=case_id,
        title=title,
        inputs=inputs,
        assumptions=tuple(assumptions),
        metadata=metadata,
        input_units=input_units,
        input_sources=input_sources,
    )


def _validate_json_numbers(value: Any, path: str) -> None:
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{path} contains a non-finite number")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_numbers(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_json_numbers(item, f"{path}.{key}")
