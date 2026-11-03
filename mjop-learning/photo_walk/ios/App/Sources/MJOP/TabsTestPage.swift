#if DEBUG
import Foundation

/// ALLEEN VOOR UI-TESTS (Debug-build, argument `-mjop-tabs-test-page`): een lokale, nagebootste website die de native navigatie kent. Geen netwerk.
/// De "projecten" hieronder zijn testgegevens en bestaan niet in de Release-app (die laadt altijd de echte website en haalt de projecten uit de backend).
/// Gedrag volgt het contract in `docs/mjop_integration.md` / `contract_v1.json`: meldt zich met `webReady`, antwoordt op commando's met `webReply`
/// en stuurt `webState`. Een project wisselen terwijl er al een project open is, geeft UNSAVED_CHANGES tenzij `force` (zoals de echte website bij niet-opgeslagen werk).
extension MJOPWebController {
    static let tabsTestPageHTML = """
    <!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
    <h1>MJOP tabs-testpagina</h1>
    <p id="pageid">Pagina-id: -</p>
    <button onclick="n++;show()">Teller verhogen</button>
    <p id="c">Teller: 0</p>
    <button onclick="sessionStorage.setItem('tabtest','sessie-bewaard');localStorage.setItem('tabtest-login','ingelogd-bewaard');readStorage()">Opslag schrijven</button>
    <button onclick="readStorage()">Opslag lezen</button>
    <p id="storage">Opslag: leeg</p>
    <p id="tab">Tabblad: home</p>
    <p id="proj">Project: geen</p>
    <p id="login">Ingelogd: ja</p>
    <p id="lastcmd">Laatste commando: geen</p>
    <button onclick="post('startPhotoRound', ctx('round'))">Start fotoronde</button>
    <script>
    var n = 0, k = 0, ready = false;
    var loadId = Math.random().toString(36).slice(2, 8);
    var A = '11111111-2222-3333-4444-555555555555', B = '66666666-7777-8888-9999-000000000000';
    var S = { loggedIn: true, planId: null, label: null, tab: 'home', dirty: false };
    var PROJECTS = [
      { id: A, label: 'Testproject A', adres: 'Teststraat 1, Testdorp', updatedAt: '2026-10-30T09:15:00Z', nextStep: 'Bekijk je voorstel' },
      { id: B, label: 'Testproject B', adres: null, updatedAt: null, nextStep: 'Open het gebouw en ga verder' }
    ];
    function el(i) { return document.getElementById(i); }
    function show() {
      el('pageid').textContent = 'Pagina-id: ' + loadId;
      el('c').textContent = 'Teller: ' + n;
      el('tab').textContent = 'Tabblad: ' + S.tab;
      el('proj').textContent = 'Project: ' + (S.label || 'geen');
      el('login').textContent = 'Ingelogd: ' + (S.loggedIn ? 'ja' : 'nee');
    }
    function readStorage() {
      var a = '-', b = '-';
      try { a = sessionStorage.getItem('tabtest') || '-'; b = localStorage.getItem('tabtest-login') || '-'; } catch (e) { a = 'fout'; b = 'fout'; }
      el('storage').textContent = 'Opslag: sessie=' + a + ' lokaal=' + b;
    }
    function post(a, p, rid) {
      k++;
      window.webkit.messageHandlers.mjopNative.postMessage({ v: 1, action: a, requestId: rid || ('t' + k), payload: p });
    }
    function status() {
      return { loggedIn: S.loggedIn, subscribed: true, planId: S.planId, hasBuilding: !!S.planId, example: false, label: S.label, tab: S.tab, screen: 'app',
               dirty: S.dirty, saveStatus: S.loggedIn ? (S.dirty ? 'PENDING' : 'SAVED') : 'NOT_LOGGED_IN', pendingProposals: 0,
               planRef: S.planId ? 'plan-0123456789abcdef01234567' : null, nextStep: S.planId ? 'Bekijk je voorstel' : null };
    }
    function push() { if (ready) post('webState', status()); }
    function ctx(mode) {
      return { planRef: 'plan-0123456789abcdef01234567', mjopPlanId: S.planId, buildingLabel: S.label || 'Testgebouw 1', bagPandId: null, mode: mode, element: null,
               plannedFacades: [{ name: 'Voorgevel', orientation: 'S' }] };
    }
    function reply(m, ok, data, err) {
      var p = { command: m.command, ok: ok };
      if (ok) p.data = data; else p.error = err;
      post('webReply', p, m.requestId);
    }
    function openPlan(id, force) {
      if (S.planId && S.planId !== id && !force) return { code: 'UNSAVED_CHANGES', message: 'Het huidige project heeft wijzigingen die nog niet zijn opgeslagen.' };
      var p = PROJECTS.filter(function (x) { return x.id === id; })[0];
      if (!p) return { code: 'OPEN_FAILED', message: 'Dit project kon niet geopend worden.' };
      S.planId = id; S.label = p.label; S.dirty = false; return null;
    }
    window.MJOPNativeBridge = { receive: function (m) {
      if (m.type === 'nativeReady') { ready = true; push(); return true; }
      if (m.type !== 'command') return false;
      el('lastcmd').textContent = 'Laatste commando: ' + m.command + (m.tab ? ' ' + m.tab : '') + (m.sub ? '/' + m.sub : '');
      var e;
      switch (m.command) {
        case 'navigate': S.tab = m.tab; show(); reply(m, true, status()); break;
        case 'getProjects':
          reply(m, true, { loggedIn: S.loggedIn, projects: S.loggedIn ? PROJECTS.map(function (x) { return Object.assign({ current: x.id === S.planId }, x); }) : [] }); break;
        case 'openProject':
          e = openPlan(m.id, m.force === true);
          if (e) reply(m, false, null, e); else { if (m.tab) S.tab = m.tab; show(); reply(m, true, status()); }
          break;
        case 'startMeasurement':
          if (m.planId && m.planId !== S.planId) { e = openPlan(m.planId, m.force === true); if (e) { reply(m, false, null, e); break; } }
          if (!S.planId) { reply(m, false, null, { code: 'NO_PROJECT', message: 'Er is geen project geopend.' }); break; }
          show(); post('startPhotoRound', ctx(m.mode === 'element' ? 'round' : m.mode)); reply(m, true, { started: true, mode: m.mode, planRef: 'plan-0123456789abcdef01234567' }); break;
        case 'getStatus': reply(m, true, status()); break;
        case 'getProposals': reply(m, true, { planRef: S.planId ? 'plan-0123456789abcdef01234567' : null, total: 0, pending: [] }); break;
        case 'signOut': S.loggedIn = false; S.planId = null; S.label = null; show(); reply(m, true, { signedOut: true }); break;
        case 'newProject': S.tab = 'start'; show(); reply(m, true, status()); break;
        default: reply(m, false, null, { code: 'INVALID_COMMAND', message: 'onbekend' });
      }
      push();
      return true;
    } };
    show();
    post('webReady', { features: ['nav1'], webVersion: 'test-1' });
    </script></body></html>
    """
}
#endif
