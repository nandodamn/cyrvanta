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

**Estado de especificación:** DRAFT PARA REVISIÓN HUMANA el 2026-07-28. Ver
`docs/specifications/PHASE_18_DETERMINISTIC_MULTI_SOURCE_CORRELATION.md`.

**Estado de implementación:** NO AUTORIZADA.

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

## Próxima decisión humana

Revisar, enmendar o aprobar el contrato DRAFT de Etapa 4 en
`docs/specifications/PHASE_18_DETERMINISTIC_MULTI_SOURCE_CORRELATION.md`. No
crear todavía tablas, contratos, handlers o endpoints. Las puertas
independientes de retención por tenant y polling periódico Wazuh continúan
abiertas.
