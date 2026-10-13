"""Tool get_kengetal_candidates: alleen-lezen opvragen van kengetal-kandidaten voor één MJOP-regel.

Hergebruikt uitsluitend bestaande leesfuncties:
  match_kengetal.load_context       leest kengetallen v1, genormaliseerde observations en vocabularies
  human_match_review.load_json      leest de beslissingenopslag
  mjop_kengetal_workflow.run        normalisatie -> matching -> actuele menselijke beslissing -> bedrag

Deze module rekent niets zelf: bedragen zijn de Decimal-strings uit de bronbestanden, ongewijzigd. Een kandidaat
zonder actieve menselijke beslissing krijgt nooit een effectief bedrag (price_presentation.is_accepted_price=false);
dat wordt zowel door het uitvoerschema als door een extra controle in deze module (fail-closed) afgedwongen.

Geen schrijfpad, geen netwerk, geen paden uit modelinvoer: de gegevensroot komt uit agent.contract.PROJECT_ROOT
(of, alleen voor tests, uit het Python-argument `root`; dat argument is niet bereikbaar via call_tool).
"""
import copy
import os

from agent.contract import (PROJECT_ROOT, ToolError, canonical_sha256, load_schema, schema_errors)

import human_match_review  # noqa: E402  (via agent.contract op sys.path)
import match_kengetal  # noqa: E402
import mjop_kengetal_workflow  # noqa: E402

NAME = "get_kengetal_candidates"
TOOL_VERSION = "agent_tool_get_kengetal_candidates_v1"
INPUT_SCHEMA_FILE = "get_kengetal_candidates.input.schema.json"
OUTPUT_SCHEMA_FILE = "get_kengetal_candidates.output.schema.json"

DECISION_STATE = {"ACCEPTED": "HUMAN_ACCEPTED", "ADJUSTED": "HUMAN_ADJUSTED", "REJECTED": "HUMAN_REJECTED"}
PRICE_LABEL = {"ACCEPTED": "HUMAN_ACCEPTED_PRICE", "ADJUSTED": "HUMAN_ADJUSTED_PRICE", "REJECTED": "REJECTED_BY_HUMAN"}
NOTICE = ("Historisch kengetal v1: niet geïndexeerd, geen marktprijs of normprijs. Een kandidaat zonder actief "
          "menselijk besluit is een voorstel en nooit een geaccepteerde prijs; alleen price_presentation."
          "is_accepted_price=true mag als bedrag worden gebruikt.")
STATEMENTS = {
    "NO_PRICE": "Er is geen kandidaat en geen menselijk besluit: geen prijs beschikbaar.",
    "SYSTEM_CANDIDATE_NOT_ACCEPTED": ("Voorstel van het systeem zonder menselijk besluit: dit is GEEN geaccepteerde "
                                      "prijs en mag niet als prijs in een plan worden gebruikt."),
    "REJECTED_BY_HUMAN": "Een mens heeft het voorstel afgewezen: geen prijs beschikbaar.",
    "HUMAN_ACCEPTED_PRICE": "Een mens heeft het kengetal geaccepteerd; bedrag uit het kengetal, niet geïndexeerd.",
    "HUMAN_ADJUSTED_PRICE": "Een mens heeft het bedrag aangepast of een ander kengetal gekozen; niet geïndexeerd.",
}

TOOL_SPEC = {
    "name": NAME,
    "description": ("Alleen-lezen. Zoekt voor één MJOP-onderhoudsregel (elementcode, actie, eenheid, materiaal) "
                    "bestaande, door mensen beoordeelde historische kengetallen en geeft per kandidaat de herleiding "
                    "(kengetal-, cluster- en observation-ID's, bronhashes). Verzint niets en rekent niets uit. Een "
                    "kandidaat zonder menselijk besluit is een voorstel en géén geaccepteerde prijs."),
    "input_schema": load_schema(INPUT_SCHEMA_FILE),
}


def _hashes(match_result, decision_store):
    h = match_result["input_hashes"]
    return {"kengetallen_output_sha256": h["kengetallen_output_sha256"],
            "normalized_observations_sha256": h["normalized_observations_sha256"],
            "decision_store_sha256": canonical_sha256(decision_store),
            "vocabularies_sha256": dict(h["vocabularies_sha256"])}


def _candidate(kengetal, evaluation, status, financial, proposed_id):
    selected = financial["human_selected_kengetal_id"] if status in ("ACCEPTED", "ADJUSTED") else None
    chosen = selected is not None and kengetal["kengetal_id"] == selected
    return {
        "kengetal_id": kengetal["kengetal_id"],
        "kengetal_status": kengetal["status"],
        "scope_status": evaluation["scope_status"],
        "scope_reasons": list(evaluation["scope_reasons"]),
        "is_proposed_candidate": kengetal["kengetal_id"] == proposed_id,
        "presentation": "HUMAN_SELECTED" if chosen else "SYSTEM_CANDIDATE_NOT_ACCEPTED",
        "is_accepted_price": chosen,
        "element_code": kengetal["element_code"],
        "action": kengetal["action"],
        "unit": kengetal["unit"],
        "material": copy.deepcopy(kengetal["material"]),
        "vat_basis": list(kengetal["vat_basis"]),
        "value_exact": kengetal["value_exact"],
        "value_display": kengetal["value_display"],
        "min_exact": kengetal["min_exact"],
        "max_exact": kengetal["max_exact"],
        "price_levels": copy.deepcopy(kengetal["price_levels"]),
        "source_cluster_ids": list(kengetal["source_cluster_ids"]),
        "source_clusters": [{"source_cluster": c["source_cluster"], "contribution_exact": c["contribution_exact"],
                             "observation_ids": list(c["observation_ids"]), "price_levels": list(c["price_levels"])}
                            for c in kengetal["cluster_contributions"]],
        "observation_ids": list(kengetal["observation_ids"]),
        "decision_ids": list(kengetal["decision_ids"]),
        "caveats": {"decision_caveats": copy.deepcopy(kengetal["decision_caveats"]),
                    "observation_caveats": copy.deepcopy(kengetal["observation_caveats"])},
    }


def _price_presentation(status, financial):
    accepted = status in ("ACCEPTED", "ADJUSTED") and financial["effective_amount"] is not None
    if accepted:
        label = PRICE_LABEL[status]
    elif status == "REJECTED":
        label = PRICE_LABEL[status]
    elif financial["system_candidate_amount"] is not None:
        label = "SYSTEM_CANDIDATE_NOT_ACCEPTED"
    else:
        label = "NO_PRICE"
    return {"label": label, "is_accepted_price": accepted,
            "effective_amount": financial["effective_amount"] if accepted else None,
            "effective_amount_unit": financial["effective_amount_unit"] if accepted else None,
            "effective_amount_source": financial["effective_amount_source"] if accepted else None,
            "system_candidate_amount": financial["system_candidate_amount"],
            "system_candidate_kengetal_id": financial["system_candidate_kengetal_id"],
            "statement": STATEMENTS[label]}


def _traceability_errors(out, kengetallen_doc, normalized_by_id):
    """Elke ID en elk bedrag in de uitvoer moet in de bronbestanden bestaan en gelijk zijn (fail-closed)."""
    errors = []
    by_id = {k["kengetal_id"]: k for k in kengetallen_doc["kengetallen"]}
    for c in out["candidates"]:
        k = by_id.get(c["kengetal_id"])
        if k is None:
            errors.append(f"{c['kengetal_id']}: kengetal bestaat niet in de bron")
            continue
        for field in ("value_exact", "value_display", "min_exact", "max_exact"):
            if c[field] != k[field]:
                errors.append(f"{c['kengetal_id']}: {field} wijkt af van de bron")
        if set(c["source_cluster_ids"]) != set(k["source_cluster_ids"]):
            errors.append(f"{c['kengetal_id']}: source_cluster_ids wijken af van de bron")
        if set(c["observation_ids"]) != set(k["observation_ids"]):
            errors.append(f"{c['kengetal_id']}: observation_ids wijken af van de bron")
        for oid in c["observation_ids"]:
            if oid not in normalized_by_id:
                errors.append(f"{c['kengetal_id']}: observation {oid} bestaat niet in de genormaliseerde bron")
        for sc in c["source_clusters"]:
            if sc["source_cluster"] not in k["source_cluster_ids"]:
                errors.append(f"{c['kengetal_id']}: cluster {sc['source_cluster']} hoort niet bij het kengetal")
            if not set(sc["observation_ids"]) <= set(c["observation_ids"]):
                errors.append(f"{c['kengetal_id']}: cluster {sc['source_cluster']} verwijst naar vreemde observations")
        if c["is_accepted_price"] and out["decision_state"] not in ("HUMAN_ACCEPTED", "HUMAN_ADJUSTED"):
            errors.append(f"{c['kengetal_id']}: als geaccepteerd gepresenteerd zonder menselijk besluit")
    pp = out["price_presentation"]
    if out["decision_state"] in ("NO_HUMAN_DECISION", "HUMAN_REJECTED") and (
            pp["is_accepted_price"] or pp["effective_amount"] is not None
            or out["financial_result"]["effective_amount"] is not None):
        errors.append("effectief bedrag zonder actief menselijk besluit")
    return errors


def get_kengetal_candidates(item, *, root=None):
    """Zie module-docstring. `root` is alleen voor tests (bijv. een vaste fixture-root) en bestaat niet in TOOL_SPEC."""
    if not isinstance(item, dict):
        raise ToolError("INVALID_INPUT", "invoer moet een JSON-object zijn")
    errors = schema_errors(item, TOOL_SPEC["input_schema"])
    if errors:
        raise ToolError("INVALID_INPUT", "invoer voldoet niet aan het inputschema", errors)
    raw = copy.deepcopy(item)
    root = os.path.abspath(root) if root else PROJECT_ROOT

    try:
        ctx = match_kengetal.load_context(root)
        store = human_match_review.load_json(mjop_kengetal_workflow.paths(root)["store"])
        result = mjop_kengetal_workflow.run(raw, store, ctx, root=root)
    except (mjop_kengetal_workflow.WorkflowError, human_match_review.IntegrityError) as e:
        raise ToolError("SOURCE_INTEGRITY_ERROR", str(e)) from e
    kengetallen_doc, normalized_by_id = ctx[0], ctx[1]

    match, status, financial = result["match_result"], result["status"], result["financial_result"]
    by_id = {k["kengetal_id"]: k for k in kengetallen_doc["kengetallen"]}
    candidates = [_candidate(by_id[e["kengetal_id"]], e, status, financial, match["candidate_kengetal_id"])
                  for e in match["candidate_evaluations"]]
    hashes = _hashes(match, store)
    out = {
        "tool": NAME,
        "tool_version": TOOL_VERSION,
        "read_only": True,
        "call_id": "AC-" + canonical_sha256({"tool_version": TOOL_VERSION, "input": raw, "source_hashes": hashes})[:16],
        "workflow_result_id": result["workflow_result_id"],
        "match_result_id": match["match_result_id"],
        "status": status,
        "decision_state": DECISION_STATE.get(status, "NO_HUMAN_DECISION"),
        "price_presentation": _price_presentation(status, financial),
        "candidates": candidates,
        "insufficient_data_kengetal_ids": list(match["provenance"]["insufficient_data_kengetal_ids"]),
        "current_decision": result["current_decision"],
        "financial_result": financial,
        "caveats": result["caveats"],
        "provenance": {"source_hashes": hashes, "kengetallen_file": match["provenance"]["kengetallen_file"],
                       "rule_versions": result["provenance"]["rule_versions"]},
        "notice": NOTICE,
    }
    problems = schema_errors(out, load_schema(OUTPUT_SCHEMA_FILE)) + _traceability_errors(out, kengetallen_doc,
                                                                                         normalized_by_id)
    if problems:
        raise ToolError("OUTPUT_CONTRACT_VIOLATION", "uitvoer voldoet niet aan contract of herleidbaarheid", problems)
    return out
