"""T11: cross-check FastAPI's generated OpenAPI schema against the committed
openapi.yaml at the repo root, so the two never silently drift apart."""

from pathlib import Path

import yaml

from app.main import app

_SPEC_PATH = Path(__file__).resolve().parent.parent.parent / "openapi.yaml"
_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _load_committed_spec() -> dict:
    with open(_SPEC_PATH) as f:
        return yaml.safe_load(f)


def test_openapi_yaml_exists_and_parses():
    assert _SPEC_PATH.exists(), f"expected {_SPEC_PATH} to exist"
    spec = _load_committed_spec()
    assert spec["openapi"].startswith("3.1")


def test_paths_and_methods_match():
    generated = app.openapi()
    committed = _load_committed_spec()

    def normalize(paths: dict) -> dict[str, set[str]]:
        return {
            path: {m for m in methods if m in _HTTP_METHODS}
            for path, methods in paths.items()
        }

    gen_norm = normalize(generated["paths"])
    committed_norm = normalize(committed["paths"])

    assert gen_norm.keys() == committed_norm.keys(), (
        f"path mismatch: in generated only={gen_norm.keys() - committed_norm.keys()}, "
        f"in committed only={committed_norm.keys() - gen_norm.keys()}"
    )
    for path in gen_norm:
        assert gen_norm[path] == committed_norm[path], f"method mismatch at {path}"


def test_operation_ids_match():
    generated = app.openapi()
    committed = _load_committed_spec()

    for path, methods in committed["paths"].items():
        for verb, op in methods.items():
            if verb not in _HTTP_METHODS:
                continue
            generated_op = generated["paths"][path][verb]
            assert generated_op.get("operationId") == op.get(
                "operationId"
            ), f"{verb.upper()} {path}"


def test_every_committed_operation_has_req_ids():
    committed = _load_committed_spec()
    for path, methods in committed["paths"].items():
        for verb, op in methods.items():
            if verb not in _HTTP_METHODS:
                continue
            assert op.get("x-req-ids"), f"{verb.upper()} {path} has no x-req-ids"
