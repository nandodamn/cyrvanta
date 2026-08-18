"""Guided demo console for Cyrvanta end-to-end scenarios.

Lab only, and deliberately outside the product: it runs in its own container
under the live-demo profile and is never part of a Cyrvanta deployment.

It executes no commands. Every check here is a network observation -- a TCP
connect, or a read-only query -- so the console cannot change the state it is
reporting on. The attack itself is not automated either: the console explains
the injection and shows the exact command, and the operator runs it, which is
what makes the demonstration attestable.

Isolation is verified by attempting a connection from outside the host rather
than by reading its firewall rules. That is the claim a client cares about --
the host is unreachable -- and it cannot be faked by the host itself.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import asyncpg

LOG = logging.getLogger("demo-console")

TENANT_ID = os.environ.get("DEMO_TENANT_ID", "")
TARGET_HOST = os.environ.get("DEMO_TARGET_HOST", "lab-server-01")
TARGET_PORT = int(os.environ.get("DEMO_TARGET_PORT", "22"))


def _dsn() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    # The application uses the SQLAlchemy driver form; asyncpg wants a plain URL.
    return raw.replace("postgresql+asyncpg://", "postgresql://")


def _reachable(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    started = datetime.now(UTC)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    elapsed = (datetime.now(UTC) - started).total_seconds() * 1000
    return True, f"conexion establecida en {elapsed:.0f} ms"


async def _query(sql: str, *args: object) -> list[dict[str, object]]:
    conn = await asyncpg.connect(_dsn())
    try:
        # Row level security scopes every read to this tenant.
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, false)", TENANT_ID)
        rows = await conn.fetch(sql, *args)
        return [dict(row) for row in rows]
    finally:
        await conn.close()


def _run(coro):
    return asyncio.run(coro)


def _checks() -> dict[str, object]:
    reachable, detail = _reachable(TARGET_HOST, TARGET_PORT)
    result: dict[str, object] = {
        "checked_at": datetime.now(UTC).isoformat(),
        "connectivity": {
            "target": f"{TARGET_HOST}:{TARGET_PORT}",
            "reachable": reachable,
            "detail": detail,
            "reading": (
                "El host responde: NO esta aislado."
                if reachable
                else "El host no responde: la contencion esta aplicada."
            ),
        },
    }
    try:
        result["incidents"] = _run(
            _query(
                """
                SELECT code, title, status, severity, created_at
                FROM incidents
                WHERE tenant_id = $1::uuid
                ORDER BY created_at DESC
                LIMIT 5
                """,
                TENANT_ID,
            )
        )
        result["executions"] = _run(
            _query(
                """
                SELECT pv.workflow_code,
                       pe.status,
                       pe.created_at,
                       (pe.result ->> 'rollback_execution_id') IS NOT NULL AS revertida
                FROM playbook_executions pe
                JOIN playbook_versions pv ON pv.id = pe.playbook_version_id
                WHERE pe.tenant_id = $1::uuid
                ORDER BY pe.created_at DESC
                LIMIT 5
                """,
                TENANT_ID,
            )
        )
    except Exception as exc:  # pragma: no cover - surfaced to the operator
        result["database_error"] = f"{type(exc).__name__}: {exc}"
    return result


PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Consola de demostracion - Cyrvanta</title>
<style>
:root{--bg:#0b1117;--panel:#131c26;--line:#243040;--text:#e6edf3;--soft:#8b98a5;
--ok:#0dd19b;--warn:#f0a020;--bad:#f05c5c;--accent:#4aa8ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:24px}
.wrap{max-width:980px;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 4px}
.lead{color:var(--soft);margin:0 0 20px}
.banner{background:rgba(240,160,32,.1);border:1px solid rgba(240,160,32,.35);
border-radius:8px;padding:10px 14px;margin-bottom:22px;font-size:.88rem}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:18px;margin-bottom:16px}
.step{display:inline-block;background:var(--accent);color:#04121f;font-weight:700;
border-radius:999px;padding:1px 10px;font-size:.78rem;margin-right:8px}
h2{font-size:1.05rem;margin:0 0 10px}
pre{background:#0a0f15;border:1px solid var(--line);border-radius:8px;padding:12px;
overflow-x:auto;font-size:.82rem;margin:10px 0}
table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:8px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--soft);font-weight:600}
button{background:var(--accent);color:#04121f;border:0;border-radius:7px;
padding:9px 16px;font-weight:600;cursor:pointer;font-size:.87rem}
button:hover{filter:brightness(1.1)}
button.ghost{background:transparent;color:var(--text);border:1px solid var(--line)}
.param{color:var(--soft);font-size:.84rem;margin:2px 0}
.param b{color:var(--text);font-weight:600}
.verdict{border-radius:8px;padding:10px 14px;margin-top:10px;font-weight:600}
.v-ok{background:rgba(13,209,155,.12);color:var(--ok)}
.v-bad{background:rgba(240,92,92,.12);color:var(--bad)}
small{color:var(--soft)}
</style></head><body><div class="wrap">

<h1>Consola de demostracion</h1>
<p class="lead">Caso 1 &mdash; Endpoint comprometido: contencion con doble aprobacion y reversion.</p>

<div class="banner">
  Entorno de laboratorio. Esta consola <b>no ejecuta comandos ni modifica nada</b>:
  solo observa por red y lee la base. La inyeccion del ataque la ejecuta el operador.
</div>

<div class="card">
  <h2><span class="step">1</span>La inyeccion</h2>
  <p>Un ataque de credenciales real desde <b>lab-workstation-01</b> hacia
  <b>lab-server-01</b>, contra la cuenta <b>analista</b>. No se fabrica ningun
  evento: se intentan accesos que <code>sshd</code> registra y Wazuh detecta.</p>
  <p>Primero, varios intentos con <b>contrasenas incorrectas</b> &mdash; el atacante
  probando a ciegas:</p>
  <pre id="cmd1"></pre>
  <div class="param"><b>analista</b> &mdash; una cuenta real del servidor. El atacante intenta
  adivinar su contrasena, que es el ataque de credenciales de manual.</div>
  <div class="param"><b>5 contrasenas incorrectas</b> &mdash; los intentos fallidos que Wazuh
  cuenta como fuerza bruta.</div>
  <div class="param"><b>sshpass -p</b> &mdash; entrega cada contrasena de forma no interactiva,
  como lo haria una herramienta de ataque.</div>
  <div class="param"><b>lab-server-01</b> &mdash; el objetivo. La IP de origen que queda registrada
  es la de la workstation, y es la clave por la que el motor agrupa los eventos.</div>
  <p style="margin-top:14px">Despues, el acceso <b>exitoso</b> con la contrasena correcta:
  el atacante finalmente entra. Los dos patrones juntos &mdash; muchos fallos y luego un
  exito, todo contra la misma cuenta y desde la misma IP &mdash; son lo que convierte esto
  en un incidente.</p>
  <pre id="cmd2"></pre>
</div>

<div class="card">
  <h2><span class="step">2</span>Estado antes de contener</h2>
  <p>Se prueba la conectividad <b>desde fuera del host</b>. Es la evidencia que importa:
  no se lee la configuracion del propio servidor, se comprueba si responde.</p>
  <button onclick="check()">Verificar estado</button>
  <button class="ghost" onclick="check()">Actualizar</button>
  <div id="out"></div>
</div>

<div class="card">
  <h2><span class="step">3</span>El tratamiento</h2>
  <p>En Cyrvanta: abrir el incidente, proponer <b>compromised-endpoint</b>, aprobar con
  <b>dos usuarios distintos</b> y ejecutar. Luego volver aqui y verificar de nuevo:
  el host debe dejar de responder.</p>
  <p><small>El canal con el SIEM se preserva a proposito: se contiene el host sin perder
  visibilidad sobre el.</small></p>
</div>

<div class="card">
  <h2><span class="step">4</span>La reversion</h2>
  <p>Revertir la ejecucion desde Cyrvanta y verificar una vez mas: la conectividad
  vuelve. La contencion es reversible y queda registrada.</p>
</div>

<script>
const CMD1 = `docker compose exec lab-workstation-01 sh -c 'for i in 1 2 3 4 5; do SSHPASS="clave-incorrecta-$i" sshpass -e ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o PreferredAuthentications=password -o PubkeyAuthentication=no analista@lab-server-01 true 2>/dev/null; done; echo "intentos fallidos enviados"'`;
const CMD2 = `docker compose exec -it lab-workstation-01 ssh -o StrictHostKeyChecking=accept-new analista@lab-server-01`;
document.getElementById('cmd1').textContent = CMD1;
document.getElementById('cmd2').textContent = CMD2;

function rows(list, cols){
  if(!list || !list.length) return '<p><small>Sin registros.</small></p>';
  const head = cols.map(c=>`<th>${c[1]}</th>`).join('');
  const body = list.map(r=>'<tr>'+cols.map(c=>`<td>${r[c[0]]??''}</td>`).join('')+'</tr>').join('');
  return `<table><tr>${head}</tr>${body}</table>`;
}

async function check(){
  const out = document.getElementById('out');
  out.innerHTML = '<p><small>Consultando...</small></p>';
  try{
    const r = await fetch('/api/checks');
    const d = await r.json();
    const c = d.connectivity;
    let html = `<div class="verdict ${c.reachable?'v-bad':'v-ok'}">${c.reading}</div>`;
    html += `<p class="param">Destino <b>${c.target}</b> &mdash; ${c.detail}</p>`;
    html += '<h3 style="font-size:.9rem;margin:16px 0 0">Incidentes recientes</h3>';
    html += rows(d.incidents, [['code','Codigo'],['title','Titulo'],['status','Estado'],['severity','Severidad']]);
    html += '<h3 style="font-size:.9rem;margin:16px 0 0">Ejecuciones de playbook</h3>';
    html += rows(d.executions, [['workflow_code','Playbook'],['status','Estado'],['revertida','Revertida']]);
    if(d.database_error) html += `<p class="param" style="color:var(--bad)">Base: ${d.database_error}</p>`;
    html += `<p><small>Verificado ${new Date(d.checked_at).toLocaleString('es')}</small></p>`;
    out.innerHTML = html;
  }catch(e){ out.innerHTML = `<p style="color:var(--bad)">Error: ${e}</p>`; }
}
</script>
</div></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "CyrvantaDemoConsole/1.0"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/health":
            self._send(200, b'{"status":"ok"}', "application/json")
            return
        if self.path == "/api/checks":
            payload = json.dumps(_checks(), default=str, ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        self._send(404, b'{"error":"not_found"}', "application/json")

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info(fmt, *args)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not TENANT_ID:
        LOG.warning("DEMO_TENANT_ID sin definir: las consultas a la base fallaran")
    port = int(os.environ.get("DEMO_CONSOLE_PORT", "8090"))
    LOG.info("consola de demostracion escuchando en %d", port)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
