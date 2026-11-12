// Maakt de pariteitsfixtures voor MJOPEngine: draait de ECHTE rekenfuncties van de website (src/app.js + src/quantity.js uit MJOP-App)
// op een reeks gebouwen en schrijft invoer + uitkomst naar Fixtures/engine_cases.json. De Swift-tests moeten exact dezelfde bedragen geven.
// Gebruik: node make_fixtures.js /pad/naar/MJOP-App
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const root = process.argv[2];
if (!root) { console.error('gebruik: node make_fixtures.js /pad/naar/MJOP-App'); process.exit(1); }
const app = fs.readFileSync(path.join(root, 'src/app.js'), 'utf8');
const Q = require(path.join(root, 'src/quantity.js'));

function grab(name) {
  const start = app.indexOf('function ' + name + '(');
  if (start < 0) throw new Error('functie niet gevonden: ' + name);
  let i = app.indexOf('{', start), depth = 0;
  for (; i < app.length; i++) { if (app[i] === '{') depth++; else if (app[i] === '}') { depth--; if (depth === 0) break; } }
  return app.slice(start, i + 1);
}
function grabVar(name) {
  const start = app.indexOf('var ' + name + ' =');
  if (start < 0) throw new Error('var niet gevonden: ' + name);
  let i = start, depth = 0, seen = false;
  for (; i < app.length; i++) {
    const c = app[i];
    if (c === '[' || c === '{') { depth++; seen = true; } else if (c === ']' || c === '}') depth--;
    if (c === ';' && depth === 0) break;
  }
  return app.slice(start, i + 1);
}

const YEAR = 2026;
const src = [
  'var CURRENT_YEAR = ' + YEAR + '; var HORIZON = 10; var cbsIndexatie = null; var INDEXATIE_PCT = 0.03;',
  grabVar('KOZ_DEF'), grabVar('KOZ_MATERIAAL'), grabVar('ELEMENT_LIBRARY'),
  ...['libraryEntry', 'bronWaarde', 'qv', 'kozAantal', 'autoForEl', 'instantiateLibraryEl', 'buildDefaultElements', 'gebrekScore', 'conditionScore',
      'kozTarief', 'kozCyclus', 'kozGroepen', 'indexeerBedrag', 'elementCost', 'nextOccurrence', 'yearForCycle', 'conditionYear', 'scheduleFor',
      'fullPlan', 'perJaarKosten', 'simuleerSaldi', 'benodigdeBijdrage'].map(grab),
  'function elementMeta() { return ""; }',
].join('\n');
const ctx = { Q, Math, console };
vm.createContext(ctx);
vm.runInContext(src, ctx);

// Gebouwen: invoer zoals de app hem heeft (BAG + 3D BAG). Null = onbekend.
const cases = [
  { name: 'singelstraat-achtig', bouwjaar: 1925, units: 1, unitsBAG: 1, footprint: 92.4, omtrek: 41.2, plat: 6, schuin: 118.35, buitenmuur: 286.5, hoogte: 7.7 },
  { name: 'portiekflat', bouwjaar: 1978, units: 8, unitsBAG: 8, footprint: 140, omtrek: 60, plat: 140, schuin: 0, buitenmuur: 520.25, hoogte: 11.4 },
  { name: 'zonder-3dbag', bouwjaar: 1965, units: 24, unitsBAG: 24, footprint: 410.5, omtrek: 102.3, plat: null, schuin: null, buitenmuur: null, hoogte: null },
  { name: 'alleen-plat', bouwjaar: 2001, units: 40, unitsBAG: 36, footprint: 800, omtrek: 140, plat: 780.6, schuin: null, buitenmuur: 1900, hoogte: 18.2 },
  { name: 'nieuwbouw-laag', bouwjaar: 2019, units: 6, unitsBAG: 6, footprint: 210, omtrek: 64, plat: 0, schuin: 240.8, buitenmuur: 410, hoogte: 6.4 },
  { name: 'bouwjaar-onbekend', bouwjaar: null, units: 12, unitsBAG: 12, footprint: 300, omtrek: 80, plat: 300, schuin: 0, buitenmuur: 700, hoogte: 9.6 },
];
const scenarios = [
  { fonds: 0, bijdrage: 55, scores: {} },
  { fonds: 25000, bijdrage: 155, scores: { 'schilderwerk-buiten': 3, 'dakgoten': 5 } },
  { fonds: 5000, bijdrage: 90, scores: { 'gevel-metselwerk': 6, 'kozijnen-onderhoud': 2, 'trappenhuis': 4 } },
];

function toB(c) {
  const b = { adres: c.name, bouwjaar: c.bouwjaar, units: c.units, unitsBron: c.unitsBAG, opp: c.footprint, omtrek: c.omtrek,
    werkhoogte: Q.workHeightFromBuildingHeight(c.hoogte), bagRaw: { footprintM2: c.footprint, omtrekM: c.omtrek }, isVoorbeeld: false };
  if (c.plat != null || c.schuin != null || c.buitenmuur != null) {
    b.d3raw = { attributes: { b3_opp_dak_plat: c.plat, b3_opp_dak_schuin: c.schuin, b3_opp_buitenmuur: c.buitenmuur } };
    b.d3 = { plat: c.plat, schuin: c.schuin, gevel: c.buitenmuur };
  } else { b.d3raw = null; b.d3 = null; }
  return b;
}
// Een score van de gebruiker wordt in de website vastgelegd als gebreken; één gebrek met som die precies die score geeft.
const GEBREK = { 1: [1, 1, 1], 2: [1, 2, 2], 3: [2, 2, 2], 4: [3, 2, 2], 5: [3, 3, 2], 6: [3, 3, 3] };

const out = [];
for (const c of cases) for (const s of scenarios) {
  const b = toB(c);
  const elements = ctx.buildDefaultElements(b);
  elements.forEach(el => { if (s.scores[el.id]) { const g = GEBREK[s.scores[el.id]]; el.gebreken = [{ ernst: g[0], omvang: g[1], intensiteit: g[2] }]; } });
  const state = { building: b, elements, fonds: s.fonds, bijdrage: s.bijdrage };
  const posten = ctx.fullPlan(state).map(p => ({ el: p.elId, jaar: p.jaar, bedrag: p.bedrag }));
  const perJaar = ctx.perJaarKosten(state);
  const saldi = ctx.simuleerSaldi(state, s.bijdrage, perJaar).map(r => ({ jaar: r.jaar, kosten: r.kosten, saldo: r.saldo }));
  out.push({
    name: c.name + ' / fonds ' + s.fonds + ' / bijdrage ' + s.bijdrage, year: YEAR, building: c, fonds: s.fonds, bijdrage: s.bijdrage, scores: s.scores,
    elements: elements.map(el => ({ id: el.id, cyclus: el.cyclus, laatsteBeurt: el.laatsteBeurt, quantity: el.quantity ? el.quantity.value : null,
      source: el.quantity ? el.quantity.source : null, cost: ctx.elementCost(el, state),
      koz: el.koz ? el.koz.map(k => k.quantity.value) : null })),
    posten, saldi, benodigdeBijdrage: ctx.benodigdeBijdrage(state),
  });
}
const file = path.join(__dirname, 'Fixtures', 'engine_cases.json');
fs.writeFileSync(file, JSON.stringify({ generated_from: 'MJOP-App src/app.js + src/quantity.js', year: YEAR, cases: out }, null, 1));
console.log('geschreven:', file, out.length, 'gevallen');
