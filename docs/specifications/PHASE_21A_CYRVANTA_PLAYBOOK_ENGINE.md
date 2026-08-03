# Fase 21-A — Cyrvanta Playbook Engine nativo

**Estado:** APROBADO PARA IMPLEMENTACIÓN  
**Fecha:** 2026-08-01  
**Implementación autorizada:** sí — ratificación humana explícita del 2026-08-01

## 1. Objetivo

Evolucionar la ejecución de playbooks aprobada en Fase 21 para incorporar un
motor nativo, seguro y controlado por Cyrvanta. n8n permanece como adaptador
opcional mientras aporte conectores o automatizaciones todavía no nativas.

## 2. Relación con Fase 21

Esta propuesta amplía `PHASE_21_N8N_WORKFLOWS_EXECUTION.md` sin sustituirlo:

- PostgreSQL continúa como sistema de registro autoritativo;
- definiciones, versiones, autorizaciones y ejecuciones pertenecen a Cyrvanta;
- los bindings separan la identidad portable de la instalación del motor;
- claim, idempotencia, auditoría, kill switches y callbacks conservan garantías;
- n8n deja de ser el único `engine_type` y pasa a ser opcional;
- la evidencia histórica `N8N` permanece inmutable.

La migración vigente restringe `automation_engine_bindings.engine_type` a
`N8N`. La implementación futura deberá ampliar el constraint mediante una nueva
migración Alembic; nunca editar una migración aplicada.

## 3. Alcance propuesto

- formato portable y versionado de playbook;
- JSON Schema y validador determinístico;
- catálogo modular de acciones nativas;
- puerto de motor, runner nativo y conectores first-party;
- ejecución asíncrona sobre RabbitMQ y workers existentes;
- API de administración, validación, publicación, dry-run y ejecución;
- secretos por referencia, nunca dentro del playbook;
- UI bilingüe de catálogo, bindings, versiones y ejecuciones;
- compatibilidad híbrida `NATIVE | N8N`;
- métricas, auditoría, pruebas de aislamiento y rollback.

## 4. Fuera de alcance v1

- clonar el editor generalista de n8n;
- JavaScript, Python, shell o binarios arbitrarios;
- plugins de terceros sin revisión y firma;
- loops, recursión o grafos sin límite;
- Redis como sistema de registro;
- secretos en JSON, PostgreSQL funcional, logs, eventos o auditoría;
- acceso directo de React a conectores;
- autorización inferida desde IA;
- retirar n8n antes de cumplir los criterios de salida.

## 5. Principios obligatorios

1. Cyrvanta autoriza; el motor sólo ejecuta una autorización vigente.
2. La IA puede proponer, pero nunca publica ni ejecuta.
3. El tenant procede del contexto autenticado o envelope interno firmado.
4. Todo efecto externo requiere claim durable previo.
5. La entrega es al menos una vez; el efecto se protege con idempotencia estable.
6. Un ACK sólo significa dispatch aceptado, no efecto exitoso.
7. Las versiones publicadas son inmutables y tienen digest canónico.
8. Inputs y outputs usan schemas estrictos y límites físicos.
9. Error, timeout, drift o kill switch fallan cerrado.
10. Los secretos se resuelven justo antes de invocar el conector.
11. `NATIVE` y `N8N` implementan el mismo puerto de motor.
12. No se promete compensación si el sistema externo no la soporta.

## 6. Arquitectura propuesta

### 6.1 Componentes

- `PlaybookDefinition`: identidad lógica y propósito tenant-owned.
- `PlaybookVersion`: contrato portable, inmutable y con digest.
- `AutomationEngineBinding`: selecciona `NATIVE` o `N8N`.
- `PlaybookEnginePort`: validación, dry-run, dispatch y salud.
- `NativePlaybookEngine`: adaptador first-party.
- `NativePlaybookRunner`: intérprete restringido.
- `ActionRegistry`: catálogo allowlisted de acciones y schemas.
- `ActionConnectorPort`: interfaz de cada integración externa.
- `CredentialResolverPort`: resuelve aliases en el secret manager.
- `ExecutionPolicyEvaluator`: modo, impacto, aprobación y kill switches.
- `StepExecution`: hechos, intentos, outcomes y referencias externas.

El runner nativo se incorpora primero a los workers existentes. No se agrega un
contenedor salvo que mediciones de aislamiento o capacidad lo justifiquen.
RabbitMQ transporta solicitudes/resultados; PostgreSQL conserva estado,
outbox/inbox, claims y auditoría; Redis sólo coordinación efímera.

## 7. Formato portable v1

El artefacto canónico es JSON. YAML puede aceptarse sólo como autoría y debe
normalizarse antes de calcular el digest.

Campos raíz candidatos:

- `schema_version`, `code` y `version` SemVer;
- `title_i18n` y `description_i18n`;
- `execution_mode`: `SIMULATED | LIVE`;
- `impact_level`: `LOW | MEDIUM | HIGH | CRITICAL`;
- `input_schema_ref` y `result_schema_ref`;
- `steps`, `edges`, `timeouts` y `credential_aliases` sin valores.

### 7.1 Pasos v1

- `ACTION`: invoca una acción allowlisted.
- `CONDITION`: expresión declarativa restringida.

No se admiten loops, recursión, código, subprocesos ni acceso al entorno o
filesystem. `WAIT`, subplaybooks y fan-out dinámico quedan diferidos.

Las condiciones sólo leen rutas allowlisted de inputs y outputs ya validados.
Operadores: igualdad, desigualdad, pertenencia acotada, comparación numérica,
existencia, `and`, `or` y `not`. No hay evaluación dinámica, regex aportadas por
usuarios, red, entorno, hora del host ni secretos.

### 7.2 Límites recomendados

- 64 pasos y 128 edges por versión;
- grafo dirigido acíclico;
- 256 KiB por artefacto canónico;
- 64 KiB de input y 64 KiB de resultado normalizado;
- 4 KiB por error sanitizado;
- timeout total máximo de 900 segundos;
- timeout por acción máximo de 300 segundos;
- hasta 3 intentos sólo si la acción declara retry seguro;
- backoff con jitter y deadline absoluto.

Un tenant puede usar límites menores, nunca superar los máximos sin otra
decisión aprobada.

## 8. Catálogo de acciones

Cada acción declara nombre y versión estables, i18n ES/EN, schemas estrictos,
impacto, modos, aliases de credencial, timeout, retry, idempotencia, dry-run,
cancelación, compensación opcional, egress permitido y campos sensibles.

Catálogo inicial recomendado:

1. `notification.send`;
2. `ticket.create`;
3. `incident.report.generate`;
4. `webhook.invoke_allowlisted`;
5. `endpoint.isolate_simulated`;
6. `endpoint.isolate` sólo con aprobación operativa `LIVE` separada.

Borrar evidencia, ejecutar comandos, deshabilitar identidades o alterar
firewalls queda fuera de v1.

## 9. Estados y flujo

Estados candidatos de paso: `PENDING`, `READY`, `CLAIMED`, `RUNNING`,
`SUCCEEDED`, `FAILED`, `SKIPPED`, `CANCELLED` y `UNKNOWN`. Las transiciones
terminales son monotónicas. Intentos y outcomes son append-only; las proyecciones
pueden actualizarse transaccionalmente con outbox y auditoría.

Flujo nativo:

1. API valida permiso, tenant, autorización, policy, digest y binding.
2. La transacción crea ejecución, consume autorización y agrega outbox.
3. Worker recibe tenant, correlation, causation e idempotencia.
4. Runner revalida binding, versión, kill switches y deadline.
5. Para cada paso listo crea intento y claim durable.
6. Resuelve aliases mediante `CredentialResolverPort`.
7. Ejecuta con límites de red, tiempo y payload.
8. Valida y redacta el resultado.
9. Agrega outcome, auditoría y siguiente evento transaccionalmente.
10. Finaliza sólo desde estados terminales persistidos.

## 10. Persistencia candidata

Reutilizar las tablas de Fase 21 y justificar cada adición. Candidatos mínimos:

- ampliar `automation_engine_bindings.engine_type` a `NATIVE | N8N`;
- `playbook_step_executions` como proyección tenant-scoped;
- `playbook_step_attempts` append-only;
- `playbook_step_attempt_outcomes` append-only;
- `native_action_bindings` con configuración no secreta.

Todas usan UUID, `tenant_id`, UTC, claves compuestas con tenant y RLS habilitado
y forzado. El rol de aplicación no recibe `UPDATE`/`DELETE` sobre hechos
append-only. El contrato físico e índices requieren aprobación antes de migrar.

## 11. Secretos

- El artefacto contiene sólo aliases lógicos.
- El binding referencia configuración no secreta y `credential_key_id`.
- El valor se obtiene del secret store en tiempo de uso.
- La UI puede preparar campos enmascarados, pero nunca vuelve a leer el valor.
- Logs, eventos, errores, auditoría y métricas aplican redacción estructural.
- Rotar una credencial no cambia el digest del playbook.
- Cada credencial tiene tenant, propósito y mínimo privilegio.
- Toda prueba de conector es no destructiva y auditada.

## 12. API candidata

Endpoints tenant-scoped con permisos backend:

- `GET/POST /api/v1/playbook-definitions`;
- `GET /api/v1/playbook-definitions/{definition_id}`;
- `POST /api/v1/playbook-definitions/{definition_id}/versions`;
- `POST /api/v1/playbook-versions/{version_id}/validate`;
- `POST /api/v1/playbook-versions/{version_id}/publish`;
- `POST /api/v1/playbook-versions/{version_id}/dry-run`;
- `GET /api/v1/playbook-actions`;
- `GET/POST /api/v1/playbook-bindings`;
- `POST /api/v1/playbook-bindings/{binding_id}/probe`;
- `POST/GET /api/v1/playbook-executions`;
- `GET /api/v1/playbook-executions/{execution_id}`;
- `POST /api/v1/playbook-executions/{execution_id}/cancel` sólo si es seguro.

DTO, RFC 7807, paginación, concurrencia y límites exactos deben cerrarse antes
de implementar.

## 13. Eventos candidatos

- `security.playbook_version.validated` v1;
- `security.playbook_version.published` v1;
- `security.playbook_binding.probed` v1;
- `security.native_playbook.dispatch_requested` v1;
- `security.playbook_step.claimed` v1;
- `security.playbook_step.completed` v1;
- `security.playbook_execution.completed` v1.

Sólo identificadores, versiones, status, timestamps y códigos sanitizados; nunca
secretos, parámetros sensibles o resultados raw.

## 14. Permisos

- `playbook.view`, `playbook.author`, `playbook.review`, `playbook.publish`;
- `playbook.execute`, `playbook.cancel`;
- `automation.binding.manage`, `automation.credential.prepare`;
- `automation.live.enable` como permiso y aprobación operativa separados.

El autor no puede ser único revisor/publicador de una versión `HIGH` o
`CRITICAL`. Administrar motor o credenciales no autoriza ejecutar acciones.

## 15. Auditoría

Auditar creación, validación, revisión, publicación, retiro, binding, probe,
dry-run, policy, consumo de autorización, dispatch, claim, intento, outcome,
resultado, retry, timeout, cancelación, conciliación `UNKNOWN`, kill switches,
modo `LIVE` y rotación/prueba de alias sin valores. Cada entrada conserva tenant,
actor/servicio, correlation, causation, recurso, resultado y UTC.

## 16. Modelo de amenazas

Amenazas mínimas: artefacto alterado, bypass de tenant, replay, SSRF, exfiltración
de secretos, expresiones arbitrarias, expansión de grafo/payload, confused
deputy, timeout ambiguo, worker o mensaje comprometido, downgrade/drift y `LIVE`
sin aprobación.

Controles: digest, HMAC/firma interna, nonce, timestamps, RLS, claves compuestas,
allowlists de acciones y egress, schemas, límites, redacción, claim durable,
idempotencia, separación de funciones y kill switches.

## 17. UI e i18n

Primera entrega: formularios estructurados y grafo read-only; el editor visual
completo se difiere. Mostrar motor, versión, digest, diferencias, impacto, modo,
aprobaciones, kill switches, aliases sin valores, validación, dry-run, timeline
y `UNKNOWN` sin presentarlo como éxito. Todo texto en español e inglés.

## 18. Pruebas obligatorias

- digest determinístico, schemas estrictos, límites, DAG e inmutabilidad;
- RLS real y pruebas cross-tenant por tabla;
- binding, credencial, autorización y ejecución del mismo tenant;
- replay, nonce, timestamp, digest y callback alterados;
- SSRF, egress no permitido y redacción de secretos;
- separación autor/revisor/publicador y `LIVE` fail-closed;
- E2E `SIMULATED` con RabbitMQ/worker reales;
- claim antes del efecto, retry, timeout, crash/restart y DLQ;
- outcome tardío y conciliación `UNKNOWN`;
- paridad contractual `NATIVE`/`N8N` para un playbook soportado;
- permisos backend, i18n y ausencia de secretos en frontend.

## 19. Migración, rollout y rollback

1. Aprobar esta especificación y ADR 0017.
2. Publicar schema portable v1 y fixtures.
3. Ampliar `engine_type` sin modificar historia.
4. Crear tablas/RLS mediante migración reversible cuando estén vacías.
5. Implementar detrás de `PLAYBOOK_NATIVE_ENGINE_ENABLED=false`.
6. Validar conectores simulados y E2E.
7. Habilitar sólo por tenant y binding allowlisted.
8. Comparar en shadow/dry-run sin duplicar efectos.
9. Migrar playbooks predefinidos individualmente.
10. Mantener n8n hasta superar criterios de salida.

Rollback: kill switch, detener nuevos dispatch, retornar bindings futuros a
`N8N` mediante operación auditada, conciliar ejecuciones iniciadas, conservar
evidencia y revertir migración sólo si tablas nuevas están vacías. Nunca borrar
secretos, volumen n8n, DLQ o auditoría automáticamente.

## 20. Criterios para retirar n8n del perfil estándar

1. Todos los playbooks predefinidos tienen binding `NATIVE` validado.
2. Existe paridad E2E y validación operativa aprobada.
3. No hay dependencia contractual de conectores exclusivos de n8n.
4. Backup/restore, retry, crash recovery y DLQ están probados.
5. Seguridad, RLS, auditoría, métricas y runbooks están aprobados.
6. Existe rollback probado a un adaptador alternativo.
7. El retiro obtiene aprobación operativa explícita.

n8n puede permanecer como perfil opcional indefinidamente.

## 21. Decisiones materiales pendientes

Se recomienda aprobar conjuntamente:

1. nombre `Cyrvanta Playbook Engine`;
2. evolución de Fase 21, no reemplazo del dominio;
3. estrategia `NATIVE | N8N`;
4. PostgreSQL como única autoridad funcional;
5. JSON canónico y schema portable v1;
6. sólo `ACTION` y `CONDITION` en v1;
7. prohibir código, shell, loops y plugins no firmados;
8. límites de la sección 7.2;
9. catálogo inicial de la sección 8;
10. reutilizar workers existentes inicialmente;
11. pasos append-only y RLS forzado;
12. secretos por aliases y resolver externo;
13. API candidata de la sección 12;
14. permisos/separación de la sección 14;
15. amenazas/controles de la sección 16;
16. feature flag desactivada por defecto;
17. rollout por binding y tenant;
18. n8n opcional hasta criterios objetivos de retiro;
19. editor estructurado primero y visual completo diferido;
20. retiro de n8n con aprobación operativa separada.

## 22. Puerta de implementación

GATE superado por ratificación humana explícita el 2026-08-01. Se aprobaron las
20 decisiones, esta especificación y el ADR 0017. Las acciones `LIVE` y el
retiro de n8n conservan sus aprobaciones operativas separadas.