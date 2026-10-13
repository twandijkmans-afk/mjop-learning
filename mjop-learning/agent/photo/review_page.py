"""Statische HTML-reviewpagina (lokaal, zelfstandig, zonder externe bronnen). Toont uitsluitend VOORSTELLEN."""
import base64
import html

COLORS = {"WINDOW_OPENING": "#1f6feb", "EXTERIOR_DOOR": "#d1242f", "BALCONY_DOOR": "#bf8700", "BALCONY_STRUCTURE": "#8250df",
          "BALCONY_RAILING": "#8250df", "ROOF_WINDOW": "#1a7f37", "DORMER_OPENING": "#1a7f37", "UNKNOWN_OPENING": "#6e7781"}
LABELS = {"WINDOW_OPENING": "Kozijnopening", "EXTERIOR_DOOR": "Buitendeur", "BALCONY_DOOR": "Balkondeur", "BALCONY_STRUCTURE": "Balkon",
          "BALCONY_RAILING": "Balkonhek", "ROOF_WINDOW": "Dakraam (context)", "DORMER_OPENING": "Dakkapel (context)", "UNKNOWN_OPENING": "Onbekende opening"}
VIS = {"FULL": "volledig zichtbaar", "PARTIAL": "gedeeltelijk zichtbaar", "OCCLUDED": "afgedekt"}
STATUS = {"COMPUTED": "berekend", "NULL_NO_TYPE_ASSIGNMENT": "geen type-toewijzing", "NULL_NO_DIMENSION_REFERENCE": "geen gevalideerde maat",
          "NULL_INVALID_DIMENSIONS": "ongeldige maat", "NULL_ELEMENT_TYPE_MISMATCH": "type komt niet overeen", "NULL_NO_FULL_MEMBERS": "geen volledig zichtbare openingen"}
E = html.escape


def _fmt(v, suffix=""):
    return "&mdash;" if v is None else E(str(v)) + suffix


def render_review_page(image_png, proposal_set, quantity_state, dimension_input=None, evaluation=None, title="Photo Reviewer — voorstellen"):
    photo = proposal_set["photo"]
    w, h = photo["width_px"], photo["height_px"]
    img = "data:image/png;base64," + base64.standard_b64encode(image_png).decode("ascii")
    group_of = {}
    for g in quantity_state["groups"]:
        for k in ("observation_ids_full", "observation_ids_partial_excluded", "observation_ids_occluded_excluded"):
            for oid in g[k]:
                group_of[oid] = g["group_key"]
    rects, rows = [], []
    for p in proposal_set["proposals"]:
        x1, y1, x2, y2 = p["bbox_norm"]
        col = COLORS[p["element_type"]]
        dash = {"FULL": "", "PARTIAL": ' stroke-dasharray="8 4"', "OCCLUDED": ' stroke-dasharray="2 4"'}[p["visibility"]]
        oid = E(p["observation_id"])
        rects.append(f'<g class="box" data-id="{oid}"><rect x="{x1 * w:.1f}" y="{y1 * h:.1f}" width="{(x2 - x1) * w:.1f}" height="{(y2 - y1) * h:.1f}" '
                     f'fill="{col}" fill-opacity=".10" stroke="{col}" stroke-width="3"{dash}/>'
                     f'<text x="{x1 * w + 3:.1f}" y="{max(y1 * h - 4, 12):.1f}" fill="{col}" font-size="14" font-weight="700">{oid}</text></g>')
        unc = ", ".join(f'{E(u["code"])} ({E(u["level"])})' for u in p["uncertainties"]) or "geen opgegeven"
        parts = f' · {p["parts_visible"]} delen in 1 opening' if "parts_visible" in p else ""
        rows.append(f'<tr data-id="{oid}"><td><b>{oid}</b></td><td><span class="sw" style="background:{col}"></span>{E(LABELS[p["element_type"]])}</td>'
                    f'<td>{E(VIS[p["visibility"]])}{E(parts)}</td><td>{unc}</td><td>{E(group_of.get(p["observation_id"], "—"))}</td>'
                    f'<td class="mono">{E(", ".join(f"{v:.3f}" for v in p["bbox_norm"]))}</td></tr>')
    counts = "".join(f'<tr><td>{E(LABELS[t])}</td><td>{c["full"]}</td><td>{c["partial"]}</td><td>{c["occluded"]}</td>'
                     f'<td>{"ja" if c["counts_toward_frame_counts"] else "nee (context)"}</td></tr>'
                     for t, c in quantity_state["photo_visible_counts"]["by_type"].items())
    dims = ""
    if dimension_input:
        for r in dimension_input["dimension_references"]:
            s = r["source"]
            dims += (f'<tr><td>{E(r["type_group_key"])}</td><td>{E(LABELS[r["element_type"]])}</td><td>{E(r["outer_width_m"])} m</td>'
                     f'<td>{E(r["outer_height_m"])} m</td><td>{E(s["kind"])}</td><td>{E(s["validated_by"]["reviewer_id"])} (mens)</td></tr>')
    grp = "".join(f'<tr><td>{E(g["group_key"])}</td><td>{g["count_full"]}</td><td>{len(g["observation_ids_partial_excluded"])}</td>'
                  f'<td>{len(g["observation_ids_occluded_excluded"])}</td><td>{_fmt(g["outer_width_m"], " m")}</td><td>{_fmt(g["outer_height_m"], " m")}</td>'
                  f'<td class="num">{_fmt(g["gross_area_m2"], " m²")}</td><td>{E(STATUS[g["area_status"]])}</td></tr>' for g in quantity_state["groups"])
    t = quantity_state["totals"]
    total = (f'{E(t["photo_visible_full_gross_area_m2"])} m²' if t["complete_for_photo_visible_full"]
             else f'<span class="muted">niet volledig bekend</span> (ontbrekend: {E(", ".join(t["groups_missing_area"]) or "—")})')
    ev = ""
    if evaluation:
        ev = ('<section><h2>Evaluatie t.o.v. grondwaarheid</h2><table><tr><th>Type</th><th>TP</th><th>FP</th><th>FN</th><th>Precisie</th><th>Recall</th><th>Telfout</th></tr>' +
              "".join(f'<tr><td>{E(LABELS[k])}</td><td>{v["tp"]}</td><td>{v["fp"]}</td><td>{v["fn"]}</td><td>{_fmt(v["precision"])}</td><td>{_fmt(v["recall"])}</td><td>{v["count_error"]:+d}</td></tr>'
                      for k, v in evaluation["per_type"].items()) +
              f'</table><p class="muted">{E(evaluation["overall"]["note"])}</p></section>')
    hyp = "".join(f'<li>{E(x["hypothesis_id"])} · {E(LABELS[x["element_type"]])}: {E(x["reason"])}</li>' for x in proposal_set["hidden_element_hypotheses"])
    prov = proposal_set["provider"]
    return f"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{E(title)}</title>
<style>
:root{{--bg:#fff;--fg:#1f2328;--mut:#59636e;--line:#d1d9e0;--card:#f6f8fa;--warn:#fff8c5;--warnb:#d4a72c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0d1117;--fg:#e6edf3;--mut:#9198a1;--line:#30363d;--card:#161b22;--warn:#3b2e00;--warnb:#9e6a03}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1100px;margin:0 auto;padding:16px}}
h1{{font-size:22px;margin:8px 0}}h2{{font-size:17px;margin:24px 0 8px}}.banner{{background:var(--warn);border:1px solid var(--warnb);border-radius:8px;padding:12px 14px;margin:12px 0}}
.stage{{position:relative;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--card)}}.stage img,.stage svg{{display:block;width:100%;height:auto}}
.stage svg{{position:absolute;inset:0}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
th{{color:var(--mut);font-weight:600}}.num{{text-align:right;font-variant-numeric:tabular-nums}}.mono{{font-family:ui-monospace,monospace;font-size:12px}}.muted{{color:var(--mut)}}
.sw{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}}.scroll{{overflow-x:auto}}.box{{cursor:default}}tr.hl{{background:var(--card)}}
.big{{font-size:20px;font-weight:700}}
</style></head><body><main>
<h1>{E(title)}</h1>
<div class="banner"><b>Alle uitkomsten zijn VOORSTELLEN (review_status PROPOSED).</b> Het zijn geen geaccepteerde instances, geen bewezen gebouwtotalen en geen onderhoudshoeveelheden;
er is geen pandkoppeling, geen kengetal en geen prijs aan gekoppeld. PHOTO_VISIBLE-aantallen zeggen alleen wat op deze ene foto zichtbaar is.</div>
<p class="muted">Foto <b>{E(photo["photo_id"])}</b> · bron-SHA256 <span class="mono">{E(photo["source_sha256"][:16])}…</span> · afgeleid <span class="mono">{E(photo["derivative_sha256"][:16])}…</span> ·
provider <b>{E(prov["provider_name"])}</b> ({E(prov["adapter_id"])} {E(prov["adapter_version"])}) · voorstelset <span class="mono">{E(proposal_set["set_id"])}</span> · hoeveelhedenstaat <span class="mono">{E(quantity_state["state_id"])}</span></p>
<div class="stage"><img alt="Analysebeeld met voorstellen" src="{img}"><svg viewBox="0 0 {w} {h}" aria-label="Voorgestelde bounding boxes">{"".join(rects)}</svg></div>
<p class="muted">Doorgetrokken = volledig zichtbaar · gestreept = gedeeltelijk zichtbaar · gestippeld = afgedekt. Beweeg over een rij om het vak te markeren.</p>
<section><h2>Voorgestelde elementen</h2><div class="scroll"><table id="props"><tr><th>ID</th><th>Type</th><th>Zichtbaarheid</th><th>Onzekerheid</th><th>Typegroep</th><th>bbox (0..1)</th></tr>{"".join(rows)}</table></div></section>
<section><h2>Aantallen op deze foto (PHOTO_VISIBLE, geen gebouwtotaal)</h2><div class="scroll"><table><tr><th>Type</th><th>Volledig</th><th>Gedeeltelijk</th><th>Afgedekt</th><th>Telt mee in kozijnaantallen</th></tr>{counts}</table></div>
<p class="muted">Een opening met meerdere vaste of draaiende delen blijft één opening. Gebouwtotaal: <b>onbekend</b>.</p></section>
<section><h2>Gevalideerde buitenmaten per kozijntype</h2><div class="scroll"><table><tr><th>Typegroep</th><th>Type</th><th>Breedte</th><th>Hoogte</th><th>Bron</th><th>Gevalideerd door</th></tr>{dims or '<tr><td colspan="6" class="muted">Geen gevalideerde maten opgegeven: oppervlakte blijft leeg (null).</td></tr>'}</table></div></section>
<section><h2>Bruto kozijnoppervlakte (voorstel)</h2><div class="scroll"><table><tr><th>Typegroep</th><th>Volledig</th><th>Deels (niet meegeteld)</th><th>Afgedekt (niet meegeteld)</th><th>Breedte</th><th>Hoogte</th><th class="num">Bruto m²</th><th>Status</th></tr>{grp}</table></div>
<p>Totaal volledig zichtbare openingen op deze foto: <span class="big">{total}</span></p>
<p class="muted">Methode: buitenbreedte × buitenhoogte × aantal; glas en vaste/draaiende delen vallen binnen de buitenmaat. Gedeeltelijk zichtbare en afgedekte kozijnen worden nooit als volledig gemeten behandeld. Geen schilderoppervlak.</p></section>
{ev}
<section><h2>Verborgen elementen (hypothesen, tellen nergens mee)</h2><ul>{hyp or '<li class="muted">geen</li>'}</ul></section>
</main>
<script>document.querySelectorAll('#props tr[data-id]').forEach(function(tr){{tr.addEventListener('mouseenter',function(){{document.querySelectorAll('.box').forEach(function(b){{b.style.opacity=b.dataset.id===tr.dataset.id?1:.25}});tr.classList.add('hl')}});tr.addEventListener('mouseleave',function(){{document.querySelectorAll('.box').forEach(function(b){{b.style.opacity=1}});tr.classList.remove('hl')}})}});</script>
</body></html>
"""
