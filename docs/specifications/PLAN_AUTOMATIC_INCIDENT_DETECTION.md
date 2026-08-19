# Plan: ampliar la deteccion automatica de incidentes

Estado: EN IMPLEMENTACION — aprobado 2026-08-18. Fase 1 completa.

## Contexto

Cyrvanta abre incidentes automaticamente por una sola via: el motor
deterministico de correlacion. Hoy ese motor solo puede reconocer un escenario,
y no por falta de reglas cargadas sino por tres limites distintos, verificados
en codigo durante la sesion del 2026-08-18:

1. **Agrupa unicamente por IP de origen.** `evaluate_rule()` empieza con
   `trigger_keys = trigger.source_ip_keys()` y, si viene vacio, corta con
   `return None` (`correlation/domain/models.py`). Toda la deteccion basada en
   host —integridad de archivos, rootcheck, registro de Windows, CVE, malware—
   no tiene IP de origen, asi que **ninguna regla podria rescatarla**.

2. **Exige dos patrones distintos.** El factor `distinct_signal_pattern` es
   obligatorio (esta entre los tres primeros, que deben cumplirse todos). Una
   sola alerta critica aislada —ransomware detectado una vez, nivel 15— nunca
   abre incidente. La mayoria de plataformas SOC si lo hacen.

3. **No hay administracion de reglas.** No existe servicio ni endpoint para
   crear o publicar una version de regla: la v3 de `credential-attack` se
   inserto con SQL directo contra la base.

No hay ningun otro componente que abra incidentes. Se verifico que
`IncidentModel` se crea en exactamente dos lugares del backend: el adaptador de
correlacion y el endpoint `POST /incidents`, que exige un actor humano
autenticado. Ni `risk`, ni `threat_knowledge`, ni `ai_analysis` lo tocan.

## Principio que no se negocia

Nada de esto lo decide un modelo de IA. Una regla de correlacion determina
cuando algo se convierte en incidente y puede habilitar respuestas
automaticas: es exactamente el tipo de decision que el proyecto no delega a
inferencia. Toda la mejora es deterministica, explicable y auditable.

## Invariante de regresion

`credential-attack` v3 debe seguir funcionando **identico** al terminar cada
fase: mismos selectores (5760 / 5715), agrupacion por IP, umbral 85. Los cuatro
casos de prueba montados hoy siguen siendo validos, y el incidente
`CORR-C3710199` sigue siendo tratable. Cada fase termina con la suite completa
en verde (295 tests backend / 31 frontend al momento de escribir esto) y con
commit + push.

---

## Fase 1 — Agrupar tambien por activo

**Estado: COMPLETA** (commit `c2f6efb`, 2026-08-18). `grouping` implementado en
`CorrelationRule`/`CorrelationCandidate`/`evaluate_rule()`, parseo y validacion
en `_rule()`. 4 tests nuevos en `test_correlation.py` (asset-match,
asset-no-cruza-hosts, regresion explicita de `credential-attack` sin
`grouping`, valor desconocido rechazado). Suite completa: 299/299 backend en
verde, ruff/mypy limpios, imagen reconstruida y desplegada, `/api/v1/ready`
verificado post-deploy.

**Objetivo:** que la deteccion basada en host pueda correlacionar.

**Por que primero:** es el limite que mas cobertura desbloquea, y se puede
hacer sin cambiar el comportamiento de ninguna regla existente.

**Cambios**

- `correlation/domain/models.py`
  - Agregar `CorrelationCandidate.asset_keys()`, simetrico a `source_ip_keys()`,
    filtrando `entity.kind == "ASSET"`. El normalizador de Wazuh ya emite el
    agente como `EntityKind.ASSET` con namespace `wazuh-agent`, asi que el dato
    ya existe: hoy simplemente no se usa.
  - Agregar `CorrelationRule.grouping: str = "source_ip"` con valores
    `"source_ip"` o `"asset"`. **El default preserva el comportamiento actual**,
    de modo que toda regla ya cargada sigue agrupando igual sin tocarla.
  - En `evaluate_rule()`, elegir las claves segun `rule.grouping`. El factor
    `exact_source_ip` (40 puntos) pasa a nombrarse por la dimension usada; se
    mantiene el peso para no alterar los puntajes existentes.
- `correlation/infrastructure/repository.py`
  - Parsear `grouping` en `_rule()` con default `"source_ip"` y validacion
    estricta (valor desconocido = error, no silencio).

**Comprobaciones intermedias**

1. Test nuevo: una regla con `grouping: "asset"` correlaciona dos hallazgos FIM
   del mismo agente sin IP de origen.
2. Test nuevo: la misma regla **no** correlaciona hallazgos de agentes
   distintos.
3. Test de regresion explicito: `credential-attack` sin campo `grouping` en su
   definicion sigue agrupando por IP y produciendo el mismo puntaje.
4. Suite completa en verde.

**Commit + push.**

---

## Fase 2 — Incidente desde una sola senal critica

**Estado: COMPLETA** (2026-08-19). `min_severity: int | None` en
`CorrelationRule`, rama separada en `evaluate_rule()`, parseo en `_rule()`.
Se agrego el factor `critical_severity` (peso 45): 40 + 45 = 85, el mismo
umbral por defecto, y el maximo sigue siendo 100 como en el modo multi-senal.
En modo de senal unica `distinct_signal_pattern` y `same_time_bucket` **no se
emiten**, en vez de emitirse en cero: informar un factor fallido que la regla
nunca pidio explicaria mal la decision al analista.

**Correccion estructural incluida:** los factores obligatorios ya no se
determinan por la posicion `factors[:3]` sino por una tupla `required`
construida junto a `factors` en cada rama. Era el riesgo que este mismo
documento senalaba ("cualquier cambio en el orden de la tupla cambia en
silencio que factores son obligatorios") y quedaba activo mientras la Fase 3
agrega reglas.

Verificado: 304/304 backend, 31/31 frontend, ruff y mypy limpios, claves i18n
`exact_asset` y `critical_severity` agregadas en es/en.

**Objetivo:** que una alerta suficientemente grave abra incidente por si sola.

**Cambios**

- `correlation/domain/models.py`
  - Agregar `CorrelationRule.min_severity: int | None = None`. Cuando esta
    definido, una regla puede matchear con **un solo** miembro si su
    `severity_score` alcanza ese minimo.
  - En `evaluate_rule()`: cuando la regla es de senal unica, los factores
    obligatorios pasan a ser agrupacion + severidad. `distinct_signal_pattern`
    y `same_time_bucket` dejan de exigirse **solo en ese modo**; el modo
    multi-senal actual queda intacto.
- `correlation/infrastructure/repository.py`: parsear `min_severity`.

**Riesgo y como se contiene:** este es el cambio mas delicado, porque toca la
condicion de corte del motor. Se implementa como rama separada dentro de
`evaluate_rule()` activada solo por `min_severity`; sin ese campo el codigo
recorre exactamente el mismo camino que hoy.

**Comprobaciones intermedias**

1. Test: regla con `min_severity: 80` abre incidente con un unico hallazgo de
   severidad 84.
2. Test: la misma regla **no** dispara con severidad 79.
3. Test de regresion: `credential-attack` (sin `min_severity`) sigue exigiendo
   dos patrones distintos — un solo fallo no abre incidente.
4. Suite completa en verde.

**Commit + push.**

---

## Fase 3 — Reglas nuevas (datos, no codigo)

**Estado: COMPLETA en configuracion** (commits `26ffb43`, `a7eac04`, 2026-08-19).
Las tres reglas estan ACTIVE y el motor real las carga; queda pendiente el
disparo en vivo, que lo ejecuta el usuario.

```
credential-attack            v3 grouping=source_ip min_sev=None   (intacta)
critical-single-signal       v1 grouping=asset     min_sev=70
host-integrity-compromise    v1 grouping=asset     min_sev=None
privilege-escalation         v1 grouping=asset     min_sev=None
```

Cargadas con `python -m cyrvanta.load_correlation_rules`, cada activacion con
registro de auditoria (`correlation.rule.activated`). Suite 317/317. Incidentes
del tenant demo tras activar: 1 — el original `CORR-C3710199`, sin inundacion.

`lab-server-01` se reconstruyo con sudo: reregistrado como **ID 007** tras
`manage_agents -r 006`, y se limpio la clave SSH obsoleta en
`lab-workstation-01`.

**Objetivo:** cobertura real usando las dos capacidades anteriores.

Cada regla se escribe **verificando primero contra el Wazuh real** que
`rule.id` emite, como se hizo con 5760/5715. Nada de IDs supuestos.

| Regla | Agrupacion | Detecta |
|---|---|---|
| `host-integrity-compromise` | `asset` | FIM + rootcheck en el mismo host |
| `critical-single-signal` | `asset` | Una alerta de severidad alta (malware, ransomware) |
| `privilege-escalation` | ~~`source_ip`~~ → `asset` | Login exitoso + escalada de privilegios |

### Verificacion contra el Wazuh real (2026-08-19)

Se agrego contra los datos y el ruleset de este despliegue, sin suponer ningun
ID. Definiciones y justificacion en `backend/src/cyrvanta/load_correlation_rules.py`.

**IDs confirmados y usados**

| ID | Nivel | Severidad | Que es |
|---|---|---|---|
| 550 / 553 / 554 | 7 / 7 / 5 | 49 / 49 / 35 | syscheck de archivo: modificado, borrado, agregado |
| 592 | 8 | 56 | log truncado (anti-forense) |
| 5763 / 5712 | 10 | 70 | fuerza bruta sshd (usuario real / inexistente), `frequency=8 timeframe=120` |
| 5551 | 10 | 70 | PAM: multiples fallos, `frequency=8 timeframe=180` |
| 5404 | 10 | 70 | tres intentos fallidos de sudo |
| 5401 / 5402 / 5403 | 5 / 3 / 4 | 35 / 21 / 28 | sudo fallido / sudo a root / primer sudo del usuario |
| 5715 | 3 | 21 | sshd: autenticacion exitosa (ya emitido por `lab-server-01`) |

**Excluidos a proposito**

- **Syscheck de registro (594/597/598/750/751/752).** Pertenecen todos a
  `CYRVANTA-WINDOWS-LAB` y suman miles de eventos (750 solo: 2057). Agrupados
  por activo abririan incidente en casi toda ventana. Hay un test que lo impide
  (`test_host_integrity_rule_excludes_windows_registry_noise`).
- **CVE (23503-23508).** Una vulnerabilidad detectada no es un incidente en
  curso; 23505 solo tiene 278 eventos recurrentes.

**Correccion a la especificacion de `privilege-escalation`**

La tabla original pedia agrupar por `source_ip` sobre eventos de logon de
Windows. No es implementable y no conviene implementarlo:

1. **No hay IP.** `60118`, `67028` y `60110` no traen `data.srcip` en **ningun**
   evento (0 de 3194 verificados). Agrupar por `source_ip` nunca podria
   coincidir: la regla quedaria cargada y muerta — exactamente el defecto que
   este plan nacio para corregir.
2. **No significa ataque.** `67028` es el evento 4672 de Windows, "privilegios
   especiales asignados", que dispara en **todo** inicio de sesion de
   administrador. Emparejarlo con un logon exitoso detecta administracion
   normal, no escalada.

Se implementa el mismo comportamiento de atacante con senales que existen y
significan algo: login remoto (`5715`) mas escalada por sudo (`5402`/`5403`/
`5401`) agrupados por **activo**. Requiere `sudo` en la imagen del agente de
laboratorio (`LAB_SUDO_ENABLED`), agregado en esta fase.

Advertencia honesta: la regla es sensible por diseno. Un administrador que
legitimamente entre por SSH y ejecute sudo la dispara. En el laboratorio no hay
trafico sudo legitimo, pero un tenant productivo deberia excluir antes a sus
usuarios administrativos.

**Comprobaciones intermedias**

Por cada regla: generar el evento real en el laboratorio, confirmar el `rule.id`
en OpenSearch, cargar la regla, y verificar que se abre el incidente. Solo
entonces se pasa a la siguiente.

**Commit + push por regla**, para que cada una sea reversible por separado.

---

## Fase 4 — Administracion de reglas

**Estado: COMPLETA en servicio; endpoints DETENIDOS por aislamiento.**

Implementado en `correlation/application/rule_admin.py`: listar versiones, crear
borrador, activar (retirando la anterior en la misma transaccion) y retirar.
`definition_sha256` se calcula en el servicio. Validacion doble antes de tocar
la base: campo por campo, y ademas se parsea con el **mismo** codigo que usa el
worker (`SqlCorrelationRepository._rule`), de modo que si valida, el motor la
puede cargar. Auditoria por operacion (`drafted` / `activated` / `retired`).
`load_correlation_rules.py` ya no escribe SQL: delega en el servicio.

### Contradiccion de multitenencia — requiere decision

Los endpoints **no se expusieron**, y no por falta de tiempo:

- `correlation_rule_versions` **no tiene `tenant_id`**. Una regla es global:
  publicarla cambia la deteccion de todos los tenants.
- Los unicos roles que existen son `tenant-admin` y `viewer`, ambos por tenant.
  No hay rol de plataforma (verificado: la tabla `roles` solo tiene esos dos).

Exponer escritura bajo un permiso `correlation.manage` otorgado a
`tenant-admin` dejaria que el administrador de un tenant cambie la deteccion de
los demas. Segun la precedencia de `CLAUDE.md`, aislamiento multitenant gana
sobre cualquier spec posterior, incluida esta, asi que se detuvo y se registra
en vez de implementarse.

**Las dos salidas posibles** (decision pendiente del usuario):

1. **Reglas por tenant.** Agregar `tenant_id` a `correlation_rule_versions`,
   al indice unico parcial y al repositorio. Es lo correcto a largo plazo y lo
   mas invasivo: toca el motor y exige migrar las reglas existentes.
2. **Rol de operador de plataforma.** Crear un rol fuera del alcance de tenant
   y otorgarle `correlation.manage`. Mas barato, pero introduce un concepto de
   autorizacion que el sistema hoy no tiene.

Mientras tanto la operacion se hace con el script, que es auditado y
reproducible.

**Objetivo:** dejar de insertar reglas con SQL.

**Cambios**

- Servicio de aplicacion con: listar versiones, crear borrador, activar (que
  retira la version anterior en la misma transaccion), y retirar.
- Calculo de `definition_sha256` en el servicio, no a mano.
- Endpoints bajo permiso `correlation.manage`, con auditoria por operacion.
- Validacion de definicion antes de aceptar: selectores, umbral 0-100,
  `grouping` conocido, ventana valida.

**Comprobaciones intermedias**

1. Test: activar una version retira la anterior y deja una sola ACTIVE
   (la restriccion unica de la tabla ya lo exige; el test confirma que el
   servicio no la viola).
2. Test: una definicion invalida se rechaza antes de tocar la base.
3. Test: cada operacion deja registro de auditoria.
4. Suite completa en verde.

**Commit + push.**

---

## Fuera de alcance (deliberado)

- **Generacion automatica de reglas por IA.** Ver "Principio que no se negocia".
- **Disparo autonomo de playbooks al crearse un incidente.** Es una decision de
  gobernanza aparte: hoy `AUTOMATIC` significa "sin aprobacion humana", no "se
  dispara solo". Ampliar la deteccion no debe cambiar en silencio quien
  autoriza una respuesta.
- **Ingesta por push desde Wazuh.** Ya evaluado: requiere endpoint de entrada
  con autenticacion propia. Independiente de esta mejora.

## Orden de implementacion

Fase 1 → 2 → 3 → 4. Cada una es util por si sola y reversible. Si hay que
detenerse, el sistema queda en un estado consistente y con los cuatro casos de
prueba actuales funcionando.

---

# Manual operativo

Todo lo que sigue esta verificado en este entorno el 2026-08-18. Sin esto, una
sesion nueva pierde tiempo en cosas que no son deducibles del codigo.

## Entorno

- Windows + Git Bash. **Prefijar `MSYS_NO_PATHCONV=1`** en todo `docker compose
  exec` cuya orden contenga rutas absolutas (`/var/ossec/...`), o Git Bash las
  convierte a rutas de Windows y el comando falla con `C:/Program: No such file`.
- Tenant de trabajo: `e18357f0-2075-462b-a0ea-b1eaa1ffb5ec` (slug `demo`).
- Perfiles activos: `COMPOSE_PROFILES=core,live-demo` en `.env`.

## Correr los tests (NO es `pytest` a secas)

La imagen del backend **no incluye pytest**. Se usa un contenedor efimero con el
repositorio montado:

```bash
docker compose run --rm -T --user root -v "/c/dev/cyrvanta:/repo" backend sh -c \
  "pip install -q 'pytest>=8.3,<9' 'pytest-asyncio>=0.24,<1' >/dev/null 2>&1; \
   cd /repo/backend && PYTHONPATH=/repo/backend/src python -m pytest tests/ -q -p no:cacheprovider"
```

Los tests corren contra la base **real** del entorno, no contra una de prueba.
Toman el primer tenant (`SELECT id FROM tenants LIMIT 1`), que **no** es el
tenant demo: es `81621de5-...`. Por eso los tests de correlacion no ensucian el
incidente de la demo.

Frontend: `cd frontend && npm run typecheck && npm test`.

## Desplegar un cambio

No hay CI/CD y el backend **no monta el codigo**: corre lo que quedo horneado en
la imagen. Un cambio en Python no se ve hasta reconstruir:

**`worker` y `scheduler` NO comparten la imagen del backend.** Cada uno declara
su propio `build:` en `docker-compose.yml` (mismo Dockerfile, imagen distinta),
asi que `docker compose build backend` **no los toca** y siguen corriendo codigo
viejo sin ningun aviso. Esto es especialmente peligroso para este plan: el
worker es quien ejecuta el motor de correlacion, de modo que una regla nueva
puede parecer que "no funciona" cuando en realidad el motor desplegado ni
siquiera tiene el cambio. Verificado el 2026-08-19: tras la Fase 1 el worker
seguia con la imagen anterior.

Comando correcto para cualquier cambio en Python:

```bash
docker compose build backend worker scheduler
docker compose up -d backend worker scheduler
```

Comprobar que quedo desplegado de verdad, no solo que la imagen se construyo:

```bash
docker inspect -f '{{.Image}}' cyrvanta-worker-1
docker compose exec -T worker python -c \
  "from cyrvanta.modules.correlation.domain.models import CorrelationRule; \
   import dataclasses; \
   print({f.name: f.default for f in dataclasses.fields(CorrelationRule)})"
```

Excepcion: `demo-console` y `lab-endpoint` montan su `server.py` por volumen,
pero igual conviene `docker compose up -d --force-recreate <servicio>`.

## Anclas de codigo exactas (Fases 1 y 2)

`backend/src/cyrvanta/modules/correlation/domain/models.py`

- `CorrelationCandidate.source_ip_keys()` — filtra
  `entity.kind == "IP_ADDRESS" and entity.namespace == "source"`. El metodo
  `asset_keys()` de la Fase 1 es su gemelo filtrando `kind == "ASSET"`.
- `evaluate_rule()` — el corte por falta de agrupacion esta en
  `trigger_keys = trigger.source_ip_keys()` seguido de
  `if not trigger_keys: return None`.
- **La condicion critica a respetar** esta en la linea del `return None` final:

  ```python
  if score < rule.threshold or any(not factor.matched for factor in factors[:3]):
  ```

  `factors[:3]` son `exact_source_ip` (40), `distinct_signal_pattern` (25) y
  `same_time_bucket` (20) — suman exactamente 85, que es el umbral por defecto.
  El cuarto (`source_diversity`, 15) es opcional. **Cualquier cambio en el orden
  de la tupla `factors` cambia en silencio que factores son obligatorios.**

`backend/src/cyrvanta/modules/correlation/infrastructure/repository.py`

- `_rule()` — construye `CorrelationRule` desde el JSON. Aca se parsean
  `grouping` (Fase 1) y `min_severity` (Fase 2). Notar el helper `integer()`
  que ya valida y rechaza booleanos.
- `_candidate()` — arma `EntityReference` desde `model.entity_references`
  (lista de dicts con `kind`/`value`/`namespace`).

`backend/src/cyrvanta/modules/integrations/infrastructure/wazuh/normalizer.py`

- Linea ~151: el agente se emite como `kind=EntityKind.ASSET` con namespace
  `wazuh-agent`. **El dato para agrupar por activo ya existe**; hoy nadie lo lee.

## Cargar una version de regla

No hay servicio de administracion hasta la Fase 4. Hasta entonces:

1. Construir el JSON de definicion y calcular su sha256 **canonico**
   (`separators=(",", ":")`, sin espacios) dentro del contenedor:

   ```bash
   docker compose exec -T backend python3 -c "
   import json, hashlib
   definition = { ... }
   canonical = json.dumps(definition, separators=(',', ':'), ensure_ascii=False)
   print(canonical); print(hashlib.sha256(canonical.encode()).hexdigest())"
   ```

2. Insertar retirando la anterior **en una sola transaccion** (la tabla tiene
   indice unico parcial sobre `rule_code WHERE status='ACTIVE'`, asi que dos
   activas fallan):

   ```sql
   BEGIN;
   UPDATE correlation_rule_versions SET status='RETIRED'
    WHERE rule_code='<code>' AND status='ACTIVE';
   INSERT INTO correlation_rule_versions
     (rule_code, version, status, definition, definition_sha256, activated_at)
   VALUES ('<code>', '<n>', 'ACTIVE', '<json>'::jsonb, '<sha>', now());
   COMMIT;
   ```

## Verificar el pipeline end-to-end

```bash
# 1. Estado de los agentes (deben decir Active)
MSYS_NO_PATHCONV=1 docker compose exec -T wazuh-manager sh -c \
  "/var/ossec/bin/agent_control -l"

# 2. Que rule.id genera realmente Wazuh (NUNCA suponerlo)
docker compose exec -T backend python -c "
import urllib.request, json
q={'size':5,'sort':[{'timestamp':'desc'}],'query':{'bool':{'filter':[{'term':{'agent.name':'lab-server-01'}}]}}}
req=urllib.request.Request('http://opensearch:9200/wazuh-alerts-4.x-*/_search',
  data=json.dumps(q).encode(),headers={'Content-Type':'application/json'})
for h in json.load(urllib.request.urlopen(req,timeout=10))['hits']['hits']:
    s=h['_source']; print(s['rule']['id'], s['rule']['level'],
                          s.get('data',{}).get('srcip'), s['rule']['description'][:50])"

# 3. Incidentes del tenant demo
docker compose exec -T postgres psql -U cyrvanta -d cyrvanta -c \
  "SELECT code,title,status,classification,created_at FROM incidents
    WHERE tenant_id='e18357f0-2075-462b-a0ea-b1eaa1ffb5ec' ORDER BY created_at DESC;"
```

La ingesta corre sola cada 15s (`SCHEDULER_INTERVAL_SECONDS`). No hace falta
disparar `sync_wazuh_findings` a mano salvo para recuperar atraso historico.

## Trampas conocidas del laboratorio

1. **Reconstruir un agente lo desconecta de Wazuh.** Al reiniciar intenta
   reinscribirse con el mismo nombre y el manager rechaza por duplicado
   (`Duplicate agent name`). Desde ese momento **nada** de ese contenedor llega
   a Wazuh, en silencio. Solucion:

   ```bash
   MSYS_NO_PATHCONV=1 docker compose exec -T wazuh-manager sh -c \
     "printf 'y\n' | /var/ossec/bin/manage_agents -r <ID>"
   MSYS_NO_PATHCONV=1 docker compose exec -T lab-server-01 sh -c \
     "rm -f /var/ossec/etc/client.keys; /var/ossec/bin/wazuh-control restart"
   ```

   Verificar siempre con `agent_control -l` **antes** de concluir que un
   escenario no genero alertas.

2. **Reconstruir `lab-server-01` regenera sus claves SSH.** La workstation
   guarda la huella vieja y falla con `Host key verification failed`. Solucion:
   `docker compose exec lab-workstation-01 ssh-keygen -R lab-server-01`.

3. **La contrasena SSH del laboratorio** vive en `LAB_SSH_PASSWORD` dentro de
   `.env` (no versionado). La comparten `lab-server-01` y `demo-console`.

## Ejecutar el escenario de credenciales (Caso 1-4)

El operador humano ejecuta la inyeccion; la consola de demostracion
(`http://localhost:8090`) muestra los comandos y verifica el efecto.

```bash
# Fallos
docker compose exec lab-workstation-01 sh -c 'for i in 1 2 3 4 5; do \
  SSHPASS="clave-incorrecta-$i" sshpass -e ssh -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout=5 -o PreferredAuthentications=password -o PubkeyAuthentication=no \
  analista@lab-server-01 true 2>/dev/null; done'

# Exito (la consola genera este comando con la contrasena real)
curl -s http://localhost:8090/api/login-command
```

Un incidente nuevo e independiente requiere **otra IP de origen** o esperar a
que pase la ventana de 10 minutos: el agrupamiento es
`(regla, version, clave de agrupacion, ventana)`.
