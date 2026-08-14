# Plan de implementación de diferenciadores estratégicos

**Fecha:** 2026-07-28
**Estado:** APROBADO PARA ESPECIFICACIÓN — decisiones D-001 a D-012 aprobadas
por instrucción humana el 2026-07-28. Cada contrato de etapa conserva su propia
puerta de aprobación antes de implementar.
**Entrada:** `docs/audits/STRATEGIC_DIFFERENTIATORS_GAP_ANALYSIS.md`

## Objetivo

Incorporar correlación multi-fuente, clasificación epistemológica, decisión
segura, memoria operacional, Decision Graph y trazabilidad sin reemplazar las
funciones actuales, romper multitenancy ni acoplar el núcleo a proveedores.

## Principios

1. Mantener el monolito modular y los adaptadores actuales.
2. PostgreSQL sigue como sistema de registro; OpenSearch conserva telemetría.
3. Decision Graph será una proyección, no otro sistema de registro.
4. La IA propone y redacta; controles deterministas validan y deciden.
5. Respuesta automática desactivada por defecto.
6. Cada etapa entrega dominio, datos, contratos, seguridad, auditoría, pruebas y
   UI cuando corresponda.
7. Ningún fixture se presenta como integración o resultado real.
8. No se implementa una etapa antes de aprobar sus decisiones materiales.

## Puerta 0 — producto y gobierno

| ID | Decisión | Alternativa recomendada |
|---|---|---|
| D-001 | Usuario en varios tenants | Sí, mediante membresía explícita; permisos evaluados por tenant. |
| D-002 | Retención de evidencia | Configurable por tenant con mínimos de plataforma y borrado auditable. |
| D-003 | Taxonomía epistemológica | `FACT`, `DERIVED_FACT`, `INFERENCE`, `HYPOTHESIS`, `RECOMMENDATION`, `DECISION`, `ACTION`, `RESULT`. |
| D-004 | Validación de claims | Requerida para validar hipótesis/IA; nunca convierte inferencia en hecho. |
| D-005 | Correlación inicial | Identidad, activo, indicador y tiempo mediante reglas deterministas. |
| D-006 | Resolución de entidades | Tenant-scoped, fusiones explícitas y reversibles, nunca cross-tenant. |
| D-007 | Modos de respuesta | Recomendación, aprobación, doble aprobación y automático desactivado por defecto. |
| D-008 | Acciones iniciales | Demo reversible y acciones no destructivas hasta aprobar integraciones reales. |
| D-009 | Kill switches | Global y tenant, deny-by-default, auditados y evaluados al ejecutar. |
| D-010 | Semántica asíncrona | Al menos una vez, outbox/inbox, idempotencia y DLQ. |
| D-011 | Memoria operacional | Observacional primero; influencia solo aprobada y visible. |
| D-012 | Persistencia del grafo | Read model PostgreSQL; sin base de grafos en MVP. |

La aprobación de estas decisiones no aprueba nombres físicos. Cada etapa
producirá su especificación contractual revisable.

## Etapa 1 — trazabilidad asíncrona

**Resultado:** infraestructura común que conserva tenant, evento, correlación,
causalidad, versión e idempotencia.

**Estado de implementación:** COMPLETADA el 2026-07-28. Ver
`docs/specifications/PHASE_15_EVENT_DELIVERY_TRACEABILITY.md`.

**Entregables propuestos:**

- Envelope y semántica de entrega formalizados.
- Puerto de publicación desacoplado de RabbitMQ.
- Outbox transaccional e inbox/idempotencia.
- Worker con consumidores, retry acotado y DLQ.
- Contexto estructurado de logs y métricas base.
- Pruebas de aislamiento y replay.

**Puerta:** un evento sintético tenant-scoped se publica, consume y reintenta sin
duplicar efectos, preservando correlation y causation.

## Etapa 2 — modelo canónico y procedencia

**Resultado:** señal independiente del proveedor compatible con Wazuh y futuros
adaptadores.

**Estado de especificación:** APROBADA PARA IMPLEMENTACIÓN el 2026-07-28. Ver
`docs/specifications/PHASE_16_CANONICAL_SECURITY_MODEL_PROVENANCE.md`.

**Estado de implementación:** COMPLETADA el 2026-07-28, con ingestión real
acotada validada y polling automático deliberadamente desactivado.

**Trabajo:**

- Resolver el alcance de finding, alert, event e incidente externo.
- Formalizar procedencia, fingerprint y calidad de normalización.
- Definir activos, cuentas, indicadores, red, proceso y archivo.
- Definir límites de payload y qué permanece solo en OpenSearch.
- Mantener pruebas contractuales Wazuh y fake connectors.

**Puerta:** dos adaptadores de prueba producen el mismo contrato, sin depender
del proveedor ni poder cambiar el tenant.

## Etapa 3 — ledger de claims

**Resultado:** separación persistente y visible entre observación, derivación,
inferencia, hipótesis, recomendación, decisión, acción y resultado.

**Estado de especificación:** APROBADA PARA IMPLEMENTACIÓN el 2026-07-28. Ver
`docs/specifications/PHASE_17_CLAIM_LEDGER.md`.

**Estado de implementación:** COMPLETADA el 2026-07-28. Incluye migración
append-only con RLS, permisos explícitos, API, eventos, persistencia del análisis
Ollama/determinístico y presentación bilingüe.

**Trabajo:**

- Especificar agregado, estados, validaciones y evidencia.
- Procedencia humana, de regla o IA.
- Registrar regla/modelo/prompt sin cadena privada de razonamiento.
- Permisos, auditoría, API paginada y RFC 7807.
- Presentación bilingüe y accesible.

**Puerta:** una inferencia requiere evidencia autorizada, nunca se presenta como
hecho y no puede cruzar tenants.

## Etapa 4 — correlación determinista multi-fuente

**Resultado:** correlaciones versionadas, explicables y validables.

**Estado de especificación:** APROBADA PARA IMPLEMENTACIÓN el 2026-07-28. Ver
`docs/specifications/PHASE_18_DETERMINISTIC_MULTI_SOURCE_CORRELATION.md`.

**Estado de implementación:** COMPLETADA el 2026-07-28. Incluye motor
determinista, persistencia tenant-scoped, incidentes y claims idempotentes,
eventos durables, API, UI bilingüe y escenario canónico v2.

**Trabajo:**

- Selección acotada de candidatos y resolución tenant-scoped.
- Reglas, factores, score y ventanas versionados.
- Miembros, explicación y validación humana persistentes.
- Creación/actualización idempotente de incidentes.
- Métricas y UI después de servicios y persistencia.

**Puerta:** Wazuh y dos fixtures sintéticos generan un incidente reproducible
con miembros, factores y versión, sin LLM como autoridad.

## Etapa 5 — MITRE, riesgo y explicabilidad

**Resultado:** ATT&CK versionado, riesgo determinista y explicación basada en
evidencia.

**Estado de especificación:** APROBADO E IMPLEMENTADO el 2026-07-28. Ver
`docs/specifications/PHASE_19_MITRE_RISK_EXPLAINABILITY.md`.

**Estado de implementación:** COMPLETADA. Código real en
`backend/src/cyrvanta/modules/risk/` (cálculo determinista) y
`backend/src/cyrvanta/modules/threat_knowledge/` (catálogo MITRE STIX, mappings,
enriquecimiento/explicación de incidentes), con router montado en `main.py`.

**Trabajo:**

- Importación STIX con versión y procedencia.
- Mappings validados contra catálogo.
- Factores y pesos de riesgo aprobados.
- Explicación derivada de claims, factores y evidencia.
- IA opcional para redacción bilingüe con schema y fallback.

**Puerta:** los mismos inputs y versiones producen el mismo riesgo; cada técnica
y factor se rastrea a evidencia.

## Etapa 6 — decisión segura y aprobación

**Resultado:** evaluación determinista y aprobaciones persistentes.

**Estado de especificación:** APROBADO E IMPLEMENTADO — validado localmente el
2026-07-29. Ver `docs/specifications/PHASE_20_SAFE_DECISION_APPROVAL.md`.

**Estado de implementación:** código real en `backend/src/cyrvanta/modules/decision/`,
router montado en `main.py`. El spec deja el **modo `live`** de ejecución de la
decisión bloqueado como puerta independiente, separada de la aprobación del
contrato — ver "Próxima decisión humana" más abajo.

**Trabajo:**

- Política, propuesta, impacto, requisitos y autorización.
- Separación de solicitante/aprobador y doble control.
- Evaluar criticidad, confianza, riesgo, horario, salud y kill switches.
- Autorización breve vinculada a versión y parámetros exactos.
- Auditoría y pruebas negativas de permiso/IDOR.

**Puerta:** una acción crítica requiere actores distintos cuando corresponda y
cualquier cambio de inputs invalida la autorización.

## Etapa 7 — ejecución, rollback y resultado

**Resultado:** ejecuciones durables mediante adaptador reemplazable.

**Entrada obligatoria registrada:**
`docs/requirements/N8N_WORKFLOWS_AS_CODE_REQUIREMENTS.md`.

**Estado de especificación:** tres specs cubren esta etapa, todos aprobados:
`docs/specifications/PHASE_21_N8N_WORKFLOWS_EXECUTION.md` (APROBADO PARA
IMPLEMENTACIÓN, 2026-07-29), `PHASE_21A_CYRVANTA_PLAYBOOK_ENGINE.md` (motor
nativo, APROBADO PARA IMPLEMENTACIÓN, ratificado 2026-08-01) y
`PHASE_21B_REAL_NATIVE_ACTIONS.md` (acciones nativas reales, APROBADO POR
ALCANCE REAL-ONLY, 2026-08-13).

**Estado de implementación:**
- **Motor nativo (21-A/21-B): COMPLETADO y en uso real.** 21 playbooks
  (`ESSENTIAL_NATIVE_PLAYBOOKS` en
  `backend/src/cyrvanta/modules/playbooks/application/administration_service.py`)
  con acciones reales verificadas contra Postgres y Wazuh Active Response en
  `playbooks/infrastructure/action_registry.py`: transición de estado,
  notificación SMTP, ticket ITSM, webhook allowlisted, bloqueo/reactivación de
  cuenta, aislamiento/restauración de host, con 5 playbooks rollback
  auditados. Cubierto por tests de integración reales
  (`tests/unit/test_account_containment_actions.py`,
  `tests/unit/test_host_isolation_actions.py`).
- **Motor n8n (21): infraestructura presente, workflows sin conector real.**
  `HybridPlaybookDispatcher` (`playbooks/infrastructure/hybrid_dispatcher.py`)
  soporta ambos motores por binding, pero `n8n_enabled=False` por defecto y los
  5 workflows en `infrastructure/n8n/workflows/*.json` son shells: un webhook
  conectado directo a un nodo que siempre responde 503
  `workflow_inactive_pending_connector` (excepto `cyrvanta-simulate-user-block`,
  que reporta un resultado sintético). No hay lógica real de notificación,
  ticket o email dentro de esos workflows — activar este camino requiere que el
  cliente aporte credenciales reales de SMTP/Slack/ITSM. Para demos, el camino
  recomendado es el motor nativo (ya real).

**Trabajo:**

- Playbooks versionados y parámetros tipados.
- Ejecución persistente e idempotencia distribuida.
- n8n allowlisted y callbacks autenticados.
- Timeout, retry, cancelación, compensación y resultado confirmado.
- Kill switch inmediatamente antes del dispatch.

**Puerta:** una acción demo reversible atraviesa autorización, adaptador,
callback y resultado; el replay no duplica la acción.

## Etapa 8 — feedback y memoria gobernada

**Resultado:** outcomes y observaciones útiles sin aprendizaje autónomo.

**Estado de especificación:** APROBADO PARA IMPLEMENTACIÓN — base local
validada, ratificado 2026-08-01. Ver
`docs/specifications/PHASE_22_GOVERNED_FEEDBACK_MEMORY.md`.

**Estado de implementación:** COMPLETADA. Código real en
`backend/src/cyrvanta/modules/governed_memory/application/service.py` (~1085
líneas: feedback, candidatos de memoria, revisión, activación/desactivación,
evaluación de contexto), router montado en `main.py`.

**Trabajo:**

- Definir verdadero/falso positivo y outcomes.
- Feedback append-oriented.
- Candidatos de memoria con procedencia y vigencia.
- Revisión, aprobación, corrección, expiración y desactivación.
- Influencia explicada y métricas con tamaño de muestra.

**Puerta:** la memoria no influye sin aprobación vigente y toda modificación del
resultado queda explicada.

## Etapa 9 — Cyrvanta Decision Graph

**Resultado:** proyección navegable de evidencia a resultado.

**Estado de especificación:** NO INICIADA. No existe spec `PHASE_*` para esta
etapa (la numeración de specs va de `PHASE_15` a `PHASE_25` sin cubrir el
Decision Graph) ni módulo `decision_graph`/`graph` bajo
`backend/src/cyrvanta/modules/`. Es la única etapa del roadmap original sin
ningún trabajo de especificación registrado todavía.

**Trabajo:**

- Nodos/relaciones como referencias a agregados autoritativos.
- Proyección tenant-scoped e idempotente en PostgreSQL.
- Límites de profundidad, tamaño, período y exportación.
- API de lectura y UI con alternativa textual accesible.
- Exportación autorizada y redactada.

**Puerta:** se recorre evento → correlación → claim → riesgo → decisión → acción
→ resultado sin mezclar tenants ni duplicar la fuente de verdad.

## Etapa 10 — hardening y demo integral

**Resultado:** flujo demostrable, observable y regresionable.

**Estado de especificación:** cubierta parcialmente por
`docs/specifications/PHASE_24_REAL_RUNTIME_NO_SIMULATION.md` (APROBADO,
2026-08-13 — ninguna capacidad se presenta como `READY` sin respaldo real) y
`docs/specifications/PHASE_24_IMPLEMENTATION_HANDOFF.md` ("implementación
preparada; validación funcional manual pendiente del operador"). El trabajo de
UI relacionado está en
`docs/specifications/PHASE_23_OPERATIONAL_PULSE_RESPONSIVE_UI.md` (APROBADO,
ratificado 2026-08-01, implementado en `frontend/src/OperationalPulse.tsx`).

**Estado de implementación:** PARCIAL. Lo cubierto: el principio "sin
simulación" está aplicado de forma real en el motor nativo de playbooks (ver
Etapa 7) y en la UI de pulso operativo. Lo que sigue pendiente y sin spec
dedicado: E2E automatizado multi-fuente, carga con volúmenes aprobados,
escaneo de dependencias/secretos/contenedores (SAST), y runbooks de
backup/restore — nada de esto tiene código ni documento propio todavía.

**Trabajo:**

- E2E multi-fuente con fixtures identificados.
- PostgreSQL/RLS, RabbitMQ, OpenSearch, IA mock y n8n fake/callbacks.
- Carga con volúmenes aprobados, métricas, alertas y runbooks.
- Escaneo de dependencias, secretos, contenedores y SAST.
- Backup/restore, rollback y documentación operativa.

**Puerta:** el E2E aprobado pasa, los servicios degradan explícitamente, no hay
cruces de tenant y Docker Compose conserva la demo actual.

## Orden de especificaciones

1. Envelope, outbox/inbox e idempotencia.
2. Modelo canónico y procedencia.
3. Claims: taxonomía, ciclo y validación.
4. Entidades, reglas y correlación.
5. MITRE, mappings y riesgo.
6. Política, aprobaciones y autorización.
7. Playbooks, callbacks, ejecución y resultados.
8. Feedback, memoria, vigencia e influencia.
9. Proyección, consulta y exportación del Decision Graph.

Cada especificación incluirá dominio, modelo lógico, migración física,
API/eventos, permisos, auditoría, RLS, i18n, observabilidad, pruebas y rollback.

## No regresión

- Autenticación local y LDAP/AD continúan operativas.
- Sesión, RBAC y RLS no se debilitan.
- UI en español e inglés.
- Infraestructura tras puertos y límites explícitos.
- Ollama conserva URL y modelo configurables.
- Demo siempre marcada como sintética.
- Ninguna IA autoriza o ejecuta.
- No se agregan proveedores o servicios innecesarios.

## Estado real vs. este documento

**Nota (2026-08-13):** este roadmap había quedado desactualizado — describía la
Etapa 5 como bloqueada y no mencionaba las Etapas 6-10, mientras que los specs
individuales en `docs/specifications/` ya estaban aprobados e implementados
para las Etapas 5 a 8. La fuente de verdad de estado es siempre el spec
individual de cada fase (`docs/specifications/PHASE_*.md`), no este documento.
Esta sección se actualizó para reconciliar ambos.

## Puertas abiertas (aprobadas por instrucción humana el 2026-08-13)

- **PHASE_25 (ingesta automática de Wazuh):** estaba en DRAFT, sin autorizar
  implementación. Aprobada para implementación — pendiente de desarrollo
  (agregar polling al `scheduler.py` existente).
- **PHASE_20 / PHASE_21 (modo `live` de decisión y de n8n):** ambos specs
  dejan el modo `live` bloqueado como puerta separada de su aprobación de
  contrato. Aprobados para avanzar — n8n requiere además que el cliente
  aporte credenciales reales de un SMTP/Slack/ITSM propio, ya que los
  workflows de `infrastructure/n8n/` son shells sin conector real.
- **Etapa 9 (Cyrvanta Decision Graph):** sin spec, sin implementación. No hay
  todavía una decisión humana pendiente porque no se llegó a redactar el
  contrato — es el próximo hueco real del roadmap original.
- **Etapa 10 (hardening):** retención por tenant, E2E automatizado, SAST y
  runbooks de backup/restore siguen sin spec ni implementación.
