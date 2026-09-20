import json
import shutil
import subprocess

import pytest

from llmlang.a1 import interpret
from llmlang.a1.target import emit_javascript


def consumer_module(record, entry):
    return {
        "format": "a1-ir-v1",
        "types": [
            {
                "kind": "record",
                "name": record,
                "fields": [{"name": "label", "type": {"kind": "text", "capacity": 32}}],
            }
        ],
        "entries": [entry],
        "functions": [
            {
                "name": "label",
                "params": [{"name": "item", "type": record}],
                "body": [
                    {
                        "op": "record_get",
                        "dest": "%0",
                        "record": record,
                        "field": "label",
                        "value": {"ref": "item"},
                    },
                    {
                        "op": "text_prefix_codepoints",
                        "dest": "%1",
                        "value": {"ref": "%0"},
                        "count": 4,
                    },
                ],
                "return": "%1",
            },
            {
                "name": entry,
                "params": [{"name": "items", "type": {"kind": "list", "capacity": 4}}],
                "body": [
                    {
                        "op": "bounded_map",
                        "dest": "%0",
                        "list": {"ref": "items"},
                        "callback": "label",
                    }
                ],
                "return": "%0",
            },
        ],
    }


@pytest.mark.skipif(shutil.which("node") is None, reason="Node target unavailable")
@pytest.mark.parametrize(
    ("record", "entry", "capacity", "labels"),
    [
        ("Customer", "crm", 2, ["Grüße", "Zoë"]),
        ("Order", "orders", 4, ["📦-100", "Äpfel", "東京便"]),
    ],
)
def test_two_consumers_match_generated_target(record, entry, capacity, labels):
    module = consumer_module(record, entry)
    value = {
        "list": [{"record": record, "fields": {"label": item}} for item in labels],
        "capacity": capacity,
    }
    reference = interpret(module, entry, [value])
    completed = subprocess.run(
        ["node", "-e", emit_javascript(module, entry, [value])],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == reference
    assert [len(item.encode("utf-8")) for item in reference["list"]]
