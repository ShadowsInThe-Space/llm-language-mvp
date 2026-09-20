"""Additive diagnostic-v1 envelope; phase denotes a stable error category."""


def diagnostic(item: dict[str, object]) -> dict[str, object]:
    """Preserve legacy fields; never invent source coordinates or symbol names."""
    code = str(item["code"])
    if code in {"E_PARSE", "W_PARSE", "W_LEX", "W_PROFILE"}:
        phase = "parse"
    elif code in {"E_IO", "W_IO"}:
        phase = "io"
    elif code in {"E_JSON", "E_ENCODING"}:
        phase = "transport"
    elif code in {"E_CERTIFICATE", "E_SEARCH", "E_UNPROVED", "E_OPERATOR", "E_RESULT"}:
        phase = "verify"
    elif code.startswith(("E_PROVIDER", "E_FACTORY")) or code == "E_CONFIG":
        phase = "factory"
    elif code in {"E_LIMIT", "E_RESOURCE", "W_LIMIT"}:
        phase = "resource"
    elif code == "W_TARGET":
        phase = "target"
    elif code in {"E_PRECONDITION", "E_OUTPUT"}:
        phase = "execute"
    else:
        phase = "validate"
    return {
        "schema": "diagnostic-v1",
        "phase": phase,
        "message": "",
        "span": None,
        "symbol": None,
        **item,
    }


def diagnostic_document(value: object) -> object:
    """Normalize nested reports, including factory feedback and CLI fallbacks."""
    if isinstance(value, list):
        return [diagnostic_document(item) for item in value]
    if isinstance(value, dict):
        result = {key: diagnostic_document(item) for key, item in value.items()}
        if isinstance(result.get("code"), str):
            return diagnostic(result)
        return result
    return value
