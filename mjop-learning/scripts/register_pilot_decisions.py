"""Registreert de 10 in ChatGPT bevestigde Maldenhof-pilotbesluiten in een apart register.

Valideert review-ID's, keuzes en source_ref_hash tegen Decision Pack v1.2.0.
Het register is GEEN HTML-export, wijzigt geen bronobservaties, de 113 overige
punten en de 48 APP-besluiten, en maakt geen instances, merges, BAG-links,
totalen of kosten.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import human_decision_pack_data as H  # noqa: E402

BASE = ROOT / "reports/frames/photo_review_map003_map004_v1"
HTML = BASE / "decision_pack/maldenhof_human_visual_decision_pack_v1.html"
SRC = BASE / "pilot_decisions/maldenhof_pilot_10_bevestigd_in_chat.json"
OUT_JSON = BASE / "pilot_decisions/maldenhof_pilot_decision_register_v1.json"
OUT_MD = BASE / "pilot_decisions/maldenhof_pilot_decision_register_v1.md"
PACK_VERSION = "human_visual_decision_pack_v1.2.0"
EXPECTED_FORMAT = "maldenhof_pilot_10_chat_confirmed_v1"
REGISTER_FORMAT = "maldenhof_pilot_decision_register_v1"

# Wat elk besluit wel/niet doet (vaste, niet-toepassende betekenis)
EFFECT = {
    "RV-SEP-001": "Bevestigt visueel: 007 en 008 zijn door metselwerk gescheiden (twee bouwkundige openingen). Geen instance, geen totaal.",
    "RV-REL-VR-027": "Kandidaat hetzelfde fysieke raam (SAME_PHYSICAL_OBJECT_CANDIDATE). Niet bewezen, niet samengevoegd, geen pandkoppeling.",
    "RV-REL-VR-020": "Alleen dezelfde gevelsectie (SAME_FACADE_SECTION). Zegt niets over hetzelfde kozijn (same_physical_frame_proven=false).",
    "RV-REL-VR-024": "Identiteit niet te beslissen; geen kandidaatrelatie vastgelegd.",
    "RV-REL-VR-026": "Correspondentie niet te beslissen; geen kandidaatrelatie vastgelegd.",
    "RV-OBS-MAP004-012": "Bevestigt alleen de aanwezigheid van een deels zichtbaar raam (PARTIAL) in de voorlopige observatie. Geen identiteit, afmeting of pand.",
    "RV-OBS-MAP003-027": "Observatie blijft onbeslist; er is een betere foto nodig. Geen deurtype vastgelegd.",
    "RV-OBS-MAP003-009": "Observatie 009 blijft ongewijzigd (label FULL blijft staan); de FULL-naar-PARTIAL correctie is afzonderlijk voorgesteld en NIET goedgekeurd.",
    "RV-OBS-MAP003-010": "Bevestigt hoofdkozijn met twee open vleugels als een enkele opening in de voorlopige observatie. Geen unieke instance.",
    "HQ-VR-001": "Bevestigt de regel: smal linker element is afzonderlijk volgens metselwerk (MAP-002/013, foto 2). Geen extra telling; photo-2 ongewijzigd.",
}
NEVER = {"creates_instance": False, "merge": False, "bag_pand_link": False, "unique_total": False, "cost": False, "changes_source_observation": False,
         "changes_app_decision": False, "same_physical_frame_proven": False}


def load_pack():
    html = HTML.read_text(encoding="utf-8")
    pack = json.loads(re.search(r"const PACK = (\{.*?\});\n\(function", html, re.S).group(1).replace("<\\/", "</"))
    assert pack["pack_version"] == PACK_VERSION, pack["pack_version"]
    return pack


def validate(src, pack):
    """Geeft lijst fouten terug (leeg = geldig)."""
    err = []
    items = {i["review_id"]: i for i in pack["items"]}
    pilot_ids = {i["review_id"] for i in pack["items"] if i.get("pilot")}
    if src.get("format") != EXPECTED_FORMAT:
        err.append("format")
    if src.get("pack_version") != PACK_VERSION:
        err.append("pack_version")
    if src.get("apply_to_instances_authorized") or src.get("merges_authorized") or src.get("bag_links_authorized") \
            or src.get("unique_totals_authorized") or src.get("costs_authorized"):
        err.append("onbevoegde verwerking aangevraagd")
    decs = src.get("pilot_decisions", [])
    if len(decs) != 10 or src.get("decision_count") != 10:
        err.append("aantal")
    seen = set()
    for d in decs:
        rid = d.get("review_id")
        if rid in seen:
            err.append(f"dubbel {rid}")
        seen.add(rid)
        it = items.get(rid)
        if it is None:
            err.append(f"onbekend {rid}")
            continue
        if rid not in pilot_ids:
            err.append(f"geen pilotpunt {rid}")
        if d.get("source_ref_hash") != it["ref_hash"]:
            err.append(f"hash {rid}")
        if d.get("decision") not in it["choices"]:
            err.append(f"keuze {rid}")
        if d.get("approval_scope") != "PILOT_REVIEW_ONLY" or d.get("approval_provenance") != "USER_EXPLICITLY_CONFIRMED_IN_CHAT":
            err.append(f"herkomst {rid}")
    if seen != pilot_ids:
        err.append("pilotset wijkt af")
    return err


def build_register(src, pack):
    items = {i["review_id"]: i for i in pack["items"]}
    regs = []
    for d in src["pilot_decisions"]:
        it = items[d["review_id"]]
        sem = it.get("relation_semantics")
        label = None
        if sem and d["decision"] == "SAME":
            label = "SAME_FACADE_SECTION" if sem["relation_type"] == H.FACADE_SECTION else "SAME_PHYSICAL_OBJECT_CANDIDATE"
        regs.append({
            "review_id": d["review_id"], "review_type": it["review_type"], "title": it["title"], "decision": d["decision"],
            "decision_label": label, "relation_type": sem["relation_type"] if sem else None,
            "source_ref_hash": d["source_ref_hash"], "source_ref_hash_validated": True, "rationale": d["rationale"],
            "claude_proposal_in_pack": it["claude_proposal"], "differs_from_claude_pack_proposal": it["claude_proposal"] != d["decision"],
            "effect": EFFECT[d["review_id"]], "related_app_decisions_unchanged": it.get("app_links", []), "never": dict(NEVER),
            "provenance": {"decision_source": "HUMAN_CHAT_CONFIRMATION", "approval_channel": "ChatGPT conversation", "via_html_form": False,
                           "is_html_export": False, "approval_provenance": d["approval_provenance"], "approval_scope": d["approval_scope"]},
        })
    regs.sort(key=lambda r: items[r["review_id"]]["pilot"]["order"])
    return {
        "format": REGISTER_FORMAT, "pack_version": PACK_VERSION,
        "status": "REGISTERED_PILOT_ONLY_NO_FURTHER_PROCESSING",
        "approval": {"statement": src["approval_statement"], "channel": src["approval_channel"], "via_html_form": False,
                     "is_html_export": False, "source_file": SRC.name,
                     "source_file_sha256": hashlib.sha256(SRC.read_bytes()).hexdigest(), "source_prepared_file": src["source_prepared_file"],
                     "also_confirmed_in_project_chat": "2026-10-13"},
        "decision_count": len(regs), "decisions": regs,
        "other_review_points_open": len(pack["items"]) - len(regs), "existing_app_decisions_open_unchanged": 48,
        "authorized": {"apply_to_instances": False, "merges": False, "bag_links": False, "unique_totals": False, "costs": False,
                       "source_observation_changes": False},
        "separate_correction_proposal": {"id": "CORR-OBS-MAP003-009-VIS-001", "from": "FULL", "to": "PARTIAL", "status": "PROPOSED_NOT_APPLIED",
                                        "approved": False},
        "relation_semantics_kept": {"SAME_FACADE_SECTION": "alleen dezelfde gevelsectie (VR-001, VR-020); nooit hetzelfde kozijn",
                                    "SAME_PHYSICAL_OBJECT_CANDIDATE": "kandidaat, niet bewezen, niet samengevoegd"},
        "follow_up_decisions_needed": [
            "Goedkeuring OBS-MAP003-009 FULL naar PARTIAL (afzonderlijk, niet toegepast)",
            "Formele verwerkingsrelatie van pilotbesluiten tot de 48 APP-besluiten (nog niet goedgekeurd)",
            "Overige 113 reviewpunten (P1 rest 44, P2 50, P3 19) blijven OPEN",
            "Eventuele verwerking van SAME-kandidaten (VR-027) naar objectidentiteit: alleen na afzonderlijk besluit",
        ],
    }


def write(reg):
    OUT_JSON.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# Maldenhof pilotbesluitenregister v1", "",
          f"Pack: `{PACK_VERSION}`. Herkomst: bevestigd door de gebruiker via ChatGPT en in de projectchat; **niet** via het HTML-formulier en geen HTML-export.", "",
          "| Review-ID | Besluit | Label | Wat het doet |", "|---|---|---|---|"]
    for r in reg["decisions"]:
        md.append(f"| {r['review_id']} | {r['decision']} | {r['decision_label'] or '-'} | {r['effect']} |")
    md += ["", f"Overige reviewpunten OPEN: {reg['other_review_points_open']}. APP-besluiten ongewijzigd OPEN: 48.",
           "Niet toegestaan en niet gedaan: instances, samenvoegingen, BAG-pandkoppelingen, unieke totalen, kosten, wijziging van bronobservaties.",
           "Correctievoorstel CORR-OBS-MAP003-009-VIS-001 (FULL naar PARTIAL): voorgesteld, niet goedgekeurd, niet toegepast.", "",
           "## Vervolgbesluiten"] + [f"- {x}" for x in reg["follow_up_decisions_needed"]]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")


def main():
    pack = load_pack()
    src = json.loads(SRC.read_text(encoding="utf-8"))
    err = validate(src, pack)
    if err:
        raise SystemExit("Validatie mislukt: " + "; ".join(err))
    write(build_register(src, pack))
    print("OK", len(src["pilot_decisions"]))


if __name__ == "__main__":
    main()
