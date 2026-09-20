"""Independent source-to-Core binding must reject proofs of another program."""

from copy import deepcopy
from dataclasses import replace

from llmlang.model import Candidate, Expr, FunctionSpec, Specification
from llmlang.pkg.binding import check_binding, check_package_certificate, verify_package
from llmlang.pkg.linker import link
from llmlang.pkg.model import Module, Package, Snapshot
from llmlang.proof import verify


def source():
    fn = FunctionSpec(
        ("Int", "Int"),
        "Int",
        Expr("bool", value=True),
        Expr("int.eq", (Expr("result"), Expr("var", value=1))),
    )
    module = Module(
        "main",
        ("first", "second"),
        (),
        ("first",),
        Specification((fn, replace(fn, ensures=Expr("bool", value=True)))),
        Candidate((Expr("var", value=1), Expr("int", value=0))),
    )
    return Snapshot("app", (Package("app", "1.0.0", (), (module,)),))


def test_binding_and_full_proof_accept_authorized_source():
    snapshot = source()
    bound = link(snapshot)
    assert check_binding(snapshot, bound)
    result = verify_package(snapshot, bound)
    assert result["status"] == "proved"
    assert check_package_certificate(snapshot, bound, result["certificate"])


def test_swapped_bodies_and_weakened_contract_rejected():
    snapshot = source()
    bound = link(snapshot)
    assert not check_binding(
        snapshot, replace(bound, candidate=Candidate(bound.candidate.bodies[::-1]))
    )
    weakened = Specification(
        tuple(replace(f, ensures=Expr("bool", value=True)) for f in bound.spec.functions)
    )
    assert not check_binding(snapshot, replace(bound, spec=weakened))


def test_correct_proof_for_different_core_is_not_source_proof():
    snapshot = source()
    bound = link(snapshot)
    other = replace(
        bound,
        spec=Specification(
            tuple(replace(f, ensures=Expr("bool", value=True)) for f in bound.spec.functions)
        ),
        candidate=Candidate((Expr("int", value=42), Expr("int", value=0))),
    )
    proof = verify(other.spec, other.candidate)
    assert proof.status == "proved"
    evidence = verify_package(snapshot, bound)["certificate"]
    evidence["core_certificate"] = proof.certificate
    assert not check_package_certificate(snapshot, other, evidence)


def test_self_consistent_rehashed_wrong_program_is_rejected():
    import hashlib
    import json

    from llmlang.parser import canonical_candidate, canonical_spec
    from llmlang.proof import baseline_hash, candidate_hash

    snapshot = source()
    bound = link(snapshot)
    other_spec = Specification(
        tuple(replace(fn, ensures=Expr("bool", value=True)) for fn in bound.spec.functions)
    )
    other_candidate = Candidate((Expr("int", value=42), Expr("int", value=99)))
    manifest = deepcopy(bound.manifest)
    manifest["baseline_hash"] = baseline_hash(other_spec)
    manifest["candidate_hash"] = candidate_hash(other_candidate)
    for i, row in enumerate(manifest["functions"]):
        row["contract"] = canonical_spec(Specification((other_spec.functions[i],)))
        row["body"] = canonical_candidate(Candidate((other_candidate.bodies[i],)))
    del manifest["bound_hash"]
    manifest["bound_hash"] = hashlib.sha256(
        b"pkg1:bound\0"
        + json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    malicious = replace(bound, spec=other_spec, candidate=other_candidate, manifest=manifest)
    proof = verify(other_spec, other_candidate)
    assert proof.status == "proved"
    evidence = {
        "format": "pkg1-proof",
        "snapshot_hash": manifest["snapshot_hash"],
        "bound_hash": manifest["bound_hash"],
        "core_certificate": proof.certificate,
    }
    assert not check_binding(snapshot, malicious)
    assert not check_package_certificate(snapshot, malicious, evidence)


def test_manifest_export_binder_and_slot_tampering_rejected():
    snapshot = source()
    bound = link(snapshot)
    for key, value in (
        ("exported", False),
        ("binder_indices", [0, 1]),
        ("core_slot", 1),
        ("name", "other"),
    ):
        manifest = deepcopy(bound.manifest)
        manifest["functions"][0][key] = value
        assert not check_binding(snapshot, replace(bound, manifest=manifest))
    bad = Candidate((Expr("var", value=0), bound.candidate.bodies[1]))
    assert not check_binding(snapshot, replace(bound, candidate=bad))


def test_checker_does_not_trust_linker_or_search(monkeypatch):
    import llmlang.pkg.linker as linker

    snapshot = source()
    bound = link(snapshot)
    evidence = verify_package(snapshot, bound)["certificate"]

    def forbidden(*args, **kwargs):
        raise AssertionError("Untrusted generator called")

    monkeypatch.setattr(linker, "link", forbidden)
    monkeypatch.setitem(__import__("sys").modules, "llmlang.solver", None)
    assert check_binding(snapshot, bound)
    assert check_package_certificate(snapshot, bound, evidence)


def test_malformed_and_stale_evidence_rejected():
    snapshot = source()
    bound = link(snapshot)
    evidence = verify_package(snapshot, bound)["certificate"]
    for malformed in (
        None,
        [],
        {},
        {**evidence, "extra": True},
        {**evidence, "snapshot_hash": "0" * 64},
    ):
        assert not check_package_certificate(snapshot, bound, malformed)
    module = snapshot.packages[0].modules[0]
    changed = replace(module, exports=("first", "second"))
    other = replace(snapshot, packages=(replace(snapshot.packages[0], modules=(changed,)),))
    assert not check_package_certificate(other, link(other), evidence)
