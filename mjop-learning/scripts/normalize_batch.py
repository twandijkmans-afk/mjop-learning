#!/usr/bin/env python3
"""
normalize_batch.py  (stap 8 van de pipeline: EXTRACTED -> NORMALIZED)

In tegenstelling tot extract_batch.py IS dit script wel echt werkend: het
bevat geen LLM-call, alleen deterministische logica (woordenboek-lookup en
decimal-rekenwerk), precies zoals CLAUDE.md voorschrijft ("berekeningen
altijd deterministisch, nooit door het taalmodel").

Wat dit script doet per element/maintenance_action in data/extracted/*.json:
  1. Zoekt original_value op in de bijpassende vocabulaire (vocabularies/*.json).
     - Exacte match (case-insensitive) -> normalized_value invullen.
     - Geen match -> normalized_value=null, requires_human_review=True.
       (NOOIT gokken/fuzzy-matchen zonder menselijke controle, zie CLAUDE.md.)
  2. Berekent bij maintenance_actions, als quantity en unit_cost beide
     aanwezig zijn: direct_cost_calculated = quantity x unit_cost (Decimal).
     Als het document ook een total_cost_as_stated bevat en dat wijkt af van
     de berekening: cost_conflict=True + requires_human_review=True (nooit
     automatisch een van de twee kiezen).
  3. Berekent het omgekeerde als er GEEN unit_cost.value is maar wel een
     total_cost_as_stated en quantity: unit_cost_calculated = total / quantity
     (Decimal) - maar alleen als de genormaliseerde eenheid deelbaar is (niet
     'lump_sum'/stelpost, niet onbekend). Dit levert een kental op uit
     documenten die alleen een totaalbedrag per post vermelden, zonder zelf
     iets te verzinnen (het is een deling van twee al-bekende getallen) en
     zonder een niet-deelbare stelpost als "prijs per eenheid" te presenteren.
  4. Lost kale "schilderwerk"-actieteksten (buiten/binnen niet gespecificeerd)
     op via het gekoppelde element (derive_action_from_linked_element) i.p.v.
     ze allemaal handmatig te laten controleren - zie de docstring daar.
     Nested review-vlaggen (op action["action"]/action["unit"]/
     obs["defect"]) worden opgeteld naar het top-level requires_human_review
     van de action/observation, zodat de menselijke review-wachtrij niet
     stilzwijgend posten mist.

Gebruik:
    python3 scripts/normalize_batch.py --batch batch_1
"""
import argparse
import glob
import json
import os
from decimal import Decimal, InvalidOperation


def load_vocab(vocab_dir, name):
    path = os.path.join(vocab_dir, f"{name}.json")
    if not os.path.exists(path):
        return {}
    doc = json.load(open(path))
    lookup = {}
    for entry in doc.get("entries", []):
        norm = entry.get("normalized_value")
        for orig in entry.get("known_original_values", []):
            lookup[str(orig).strip().lower()] = norm
    return lookup


def normalize_pair(pair, lookup):
    """pair = {"original_value": ..., "normalized_value": ...}"""
    if not pair or not pair.get("original_value"):
        return pair
    key = str(pair["original_value"]).strip().lower()
    if key in lookup:
        pair["normalized_value"] = lookup[key]
    else:
        pair["normalized_value"] = None  # niet gokken
        pair["requires_human_review"] = True
    return pair


def to_decimal(v):
    """Parseert een bedrag/hoeveelheid naar Decimal. Moet zowel schone
    decimaalstrings ('1815.00') als letterlijk uit het document overgenomen,
    Nederlands opgemaakte bedragen aankunnen ('€ 17.910', '1.815,00') - beide
    komen voor, afhankelijk van of een veld door normalize_batch zelf is
    geschreven of letterlijk (total_cost_as_stated) uit de bron komt."""
    if v is None or v == "":
        return None
    s = str(v).strip().replace("€", "").replace("\xa0", "").replace(" ", "")
    if not s:
        return None
    try:
        if "," in s:
            # Nederlands: punt = duizendtal-scheiding, komma = decimaal
            s = s.replace(".", "").replace(",", ".")
        elif "." in s and len(s.split(".")[-1]) == 3:
            # bijv. "17.910" - geen decimalen genoemd, punt is hier
            # duizendtal-scheiding (geldbedragen hebben altijd 2 decimalen,
            # nooit 3 - dat onderscheidt dit betrouwbaar van een decimaalpunt)
            s = s.replace(".", "")
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


# Genormaliseerde eenheden waarvoor een "prijs per eenheid" geen betekenis
# heeft (stelpost/lump sum is per definitie niet deelbaar).
NON_DIVISIBLE_UNITS = {"lump_sum"}

# Voorvoegsels van element_type.original_value die ondubbelzinnig aangeven
# of een gekoppeld schilderwerk-element buiten- of binnenschilderwerk is.
PAINTING_ELEMENT_PREFIXES = {
    "buitenschilderwerk": "exterior_painting",
    "binnenschilderwerk": "interior_painting",
}


def derive_action_from_linked_element(action, element_by_id):
    """Lost de "schilderwerk"-post zonder buiten/binnen-aanduiding deterministisch
    op via het gekoppelde element, i.p.v. het aan een mens over te laten.

    vocabularies/maintenance_action.json laat kale 'schilderwerk'-teksten
    bewust ongemapt (normalized_value=null), omdat de actietekst zelf niet
    zegt of het om buiten- of binnenschilderwerk gaat (zie de notes bij de
    "paint"-entry aldaar). Maar de post is altijd gekoppeld aan een element
    (action["element_id"]), en diens element_type.original_value
    begint in de praktijk vrijwel altijd met "Buitenschilderwerk" of
    "Binnenschilderwerk". Dat is geen gok: het antwoord staat al, letterlijk,
    elders in hetzelfde record. Dit raadpleegt dus alleen reeds bekende data
    binnen hetzelfde document, net als de bestaande kostenberekeningen
    hierboven, en verzint niets.

    Grijpt alleen in als de gewone vocabulaire-lookup (normalize_pair) geen
    normalized_value heeft gevonden en de actietekst "schilderwerk" bevat.
    Bij een niet-ondubbelzinnig gekoppeld element (bijv. een kitvoeg- of
    kozijn-element dat toevallig "schilderwerk" in de actietekst noemt)
    blijft normalized_value=null en requires_human_review=True staan, exact
    zoals normalize_pair dat al had gezet.
    """
    action_pair = action.get("action") or {}
    if action_pair.get("normalized_value") is not None:
        return action
    original = str(action_pair.get("original_value") or "").strip().lower()
    if "schilderwerk" not in original:
        return action

    element = element_by_id.get(action.get("element_id"))
    if not element:
        return action
    element_type = str((element.get("element_type") or {}).get("original_value") or "").strip().lower()

    for prefix, normalized in PAINTING_ELEMENT_PREFIXES.items():
        if element_type.startswith(prefix):
            action_pair["normalized_value"] = normalized
            action_pair["requires_human_review"] = False
            action_pair["normalization_source"] = "derived_from_linked_element_type"
            return action
    return action


def normalize_maintenance_action(action):
    qty = to_decimal((action.get("quantity") or {}).get("value"))
    unit_cost_field = action.get("unit_cost") or {}
    unit_cost = to_decimal(unit_cost_field.get("value"))
    stated_dec = to_decimal(action.get("total_cost_as_stated"))

    if qty is not None and unit_cost is not None:
        direct_cost = (qty * unit_cost).quantize(Decimal("0.01"))
        action["direct_cost_calculated"] = str(direct_cost)

        if stated_dec is not None and stated_dec != direct_cost:
            action["cost_conflict"] = True
            action["requires_human_review"] = True

    action.setdefault("unit_cost_calculated", None)
    if unit_cost is None and qty is not None and qty != 0 and stated_dec is not None:
        unit_normalized = (action.get("unit") or {}).get("normalized_value")
        if unit_normalized and unit_normalized not in NON_DIVISIBLE_UNITS:
            action["unit_cost_calculated"] = str((stated_dec / qty).quantize(Decimal("0.01")))

    return action


def bubble_action_review_flag(action):
    """Zet het top-level requires_human_review van een maintenance_action als
    een genest veld (action- of eenheidsterm) niet in de vocabulaire is
    gevonden. normalize_pair zet requires_human_review alleen op de genest
    pair zelf; zonder deze stap blijft de post buiten de menselijke
    review-wachtrij terwijl normalized_value wel degelijk null is."""
    if (action.get("action") or {}).get("requires_human_review"):
        action["requires_human_review"] = True
    if (action.get("unit") or {}).get("requires_human_review"):
        action["requires_human_review"] = True
    return action


def bubble_observation_review_flag(obs):
    """Zelfde principe als bubble_action_review_flag, voor observations."""
    if (obs.get("defect") or {}).get("requires_human_review"):
        obs["requires_human_review"] = True
    return obs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="batch_1")
    ap.add_argument("--extracted-dir", default="data/extracted")
    ap.add_argument("--normalized-dir", default="data/normalized")
    ap.add_argument("--vocab-dir", default="vocabularies")
    args = ap.parse_args()

    lookups = {
        "element_type": load_vocab(args.vocab_dir, "element_type"),
        "material": load_vocab(args.vocab_dir, "material"),
        "unit": load_vocab(args.vocab_dir, "unit"),
        "defect_type": load_vocab(args.vocab_dir, "defect_type"),
        "action": load_vocab(args.vocab_dir, "maintenance_action"),
    }

    os.makedirs(args.normalized_dir, exist_ok=True)
    n_files = 0
    n_review = 0
    n_obs_review = 0

    for path in sorted(glob.glob(os.path.join(args.extracted_dir, "*.json"))):
        rec = json.load(open(path))
        if rec.get("status") == "pending_extraction":
            continue  # nog niets om te normaliseren

        for el in rec.get("elements", []):
            if "element_type" in el:
                normalize_pair(el["element_type"], lookups["element_type"])
            if "material" in el:
                normalize_pair(el["material"], lookups["material"])
            if "unit" in el:
                normalize_pair(el["unit"], lookups["unit"])

        for obs in rec.get("observations", []):
            if "defect" in obs:
                normalize_pair(obs["defect"], lookups["defect_type"])
            bubble_observation_review_flag(obs)
            if obs.get("requires_human_review"):
                n_obs_review += 1

        element_by_id = {el.get("element_id"): el for el in rec.get("elements", [])}

        for action in rec.get("maintenance_actions", []):
            if "action" in action:
                normalize_pair(action["action"], lookups["action"])
            if "unit" in action:
                normalize_pair(action["unit"], lookups["unit"])
            derive_action_from_linked_element(action, element_by_id)
            normalize_maintenance_action(action)
            bubble_action_review_flag(action)
            if action.get("requires_human_review"):
                n_review += 1

        out_path = os.path.join(args.normalized_dir, os.path.basename(path))
        json.dump(rec, open(out_path, "w"), ensure_ascii=False, indent=2)
        n_files += 1

    print(f"{n_files} bestanden genormaliseerd -> {args.normalized_dir}/")
    print(f"{n_review} maintenance_actions gemarkeerd voor menselijke controle.")
    print(f"{n_obs_review} observations gemarkeerd voor menselijke controle.")


if __name__ == "__main__":
    main()
