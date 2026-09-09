"""Provider boundary tests use a real local HTTP server, never paid inference."""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

from llmlang.adapters import FileCandidates, OpenAICompatibleProvider, ProviderError


@pytest.fixture
def model_server() -> Any:
    state: dict[str, Any] = {
        "body": {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "(candidate p0 (body 72))"},
                    "finish_reason": "stop",
                }
            ]
        },
        "status": 200,
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            state["path"] = self.path
            state["authorization"] = self.headers.get("Authorization")
            state["request"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            time.sleep(state.get("delay", 0))
            self.send_response(state["status"])
            if state["status"] == 302:
                self.send_header("Location", state["endpoint"] + "/secret-leak")
            self.end_headers()
            body = state.get("raw", json.dumps(state["body"]).encode())
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state["endpoint"] = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_file_candidates_consumes_sources_and_reads_host_paths(tmp_path: Path) -> None:
    path = tmp_path / "hello.ll"
    path.write_text("(candidate p0 (body 72))", encoding="utf-8")
    provider = FileCandidates(["(candidate p0 (body 0))", path])
    assert provider.generate({}) == "(candidate p0 (body 0))"
    assert provider.generate({}) == "(candidate p0 (body 72))"
    with pytest.raises(ProviderError, match="exhausted"):
        provider.generate({})


def test_file_candidates_enforces_bytes_before_decoding(tmp_path: Path) -> None:
    path = tmp_path / "huge.ll"
    path.write_bytes(b"x" * 20)
    provider = FileCandidates([path], max_source_bytes=10)
    with pytest.raises(ProviderError) as exc:
        provider.generate({})
    assert exc.value.code == "E_PROVIDER_SIZE"


def test_real_http_provider_sends_request_and_returns_source(model_server: Any) -> None:
    provider = OpenAICompatibleProvider(
        endpoint=model_server["endpoint"],
        model="local-test",
        api_key="TEST-SECRET",
        timeout_seconds=2,
    )
    assert (
        provider.generate({"specification": "(spec p0)", "attempt": 1})
        == "(candidate p0 (body 72))"
    )
    assert model_server["authorization"] == "Bearer TEST-SECRET"
    assert model_server["path"] == "/v1/chat/completions"
    assert model_server["request"]["model"] == "local-test"
    assert model_server["request"]["n"] == 1
    request_data = json.loads(model_server["request"]["messages"][1]["content"])
    assert request_data["specification"] == "(spec p0)"
    assert "TEST-SECRET" not in repr(provider)


@pytest.mark.parametrize(
    "body",
    [
        {"choices": []},
        {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": 72},
                    "finish_reason": "stop",
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "truncated"},
                    "finish_reason": "length",
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "user", "content": "source"},
                    "finish_reason": "stop",
                }
            ]
        },
        {
            "choices": [
                {
                    "index": True,
                    "message": {"role": "assistant", "content": "source"},
                    "finish_reason": "stop",
                }
            ]
        },
    ],
)
def test_http_provider_strictly_rejects_invalid_responses(model_server: Any, body: object) -> None:
    model_server["body"] = body
    provider = OpenAICompatibleProvider(endpoint=model_server["endpoint"], model="test")
    with pytest.raises(ProviderError) as exc:
        provider.generate({})
    assert exc.value.code == "E_PROVIDER_RESPONSE"


@pytest.mark.parametrize("raw", [b'{"choices": [], "choices": []}', b'{"choices": NaN}', b"\xff"])
def test_http_provider_rejects_duplicate_keys_nonfinite_and_invalid_utf8(
    model_server: Any, raw: bytes
) -> None:
    model_server["raw"] = raw
    provider = OpenAICompatibleProvider(endpoint=model_server["endpoint"], model="test")
    with pytest.raises(ProviderError):
        provider.generate({})


def test_http_provider_limits_bytes_and_does_not_echo_response_secrets(model_server: Any) -> None:
    model_server["raw"] = b"SECRET-IN-RESPONSE" * 100
    provider = OpenAICompatibleProvider(
        endpoint=model_server["endpoint"],
        model="test",
        api_key="TEST-SECRET",
        max_response_bytes=100,
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate({})
    assert exc.value.code == "E_PROVIDER_SIZE"
    assert "SECRET" not in str(exc.value)


def test_http_provider_refuses_redirects(model_server: Any) -> None:
    model_server["status"] = 302
    provider = OpenAICompatibleProvider(
        endpoint=model_server["endpoint"], model="test", api_key="TEST-SECRET"
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate({})
    assert exc.value.code == "E_PROVIDER_HTTP"
    assert model_server["path"] == "/v1/chat/completions"
    assert "TEST-SECRET" not in str(exc.value)


def test_http_provider_times_out_when_server_does_not_respond(model_server: Any) -> None:
    model_server["delay"] = 0.1
    provider = OpenAICompatibleProvider(
        endpoint=model_server["endpoint"], model="test", timeout_seconds=0.01
    )
    with pytest.raises(ProviderError) as exc:
        provider.generate({})
    assert exc.value.code == "E_PROVIDER_TIMEOUT"


@pytest.mark.parametrize(
    "endpoint",
    [
        "file:///etc/passwd",
        "http://example.com/v1",
        "https://user:password@example.com/v1",
        "https://example.com/v1#fragment",
    ],
)
def test_provider_rejects_unsafe_host_configuration(endpoint: str) -> None:
    with pytest.raises(ProviderError):
        OpenAICompatibleProvider(endpoint=endpoint, model="test")
