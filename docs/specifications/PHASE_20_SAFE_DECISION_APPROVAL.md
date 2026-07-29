# Fase 20 — Decisión segura, aprobaciones y autorización

**Etapa estratégica:** 6
**Estado:** APROBADO E IMPLEMENTADO — validado localmente
**Fecha:** 2026-07-29
**Implementación autorizada:** sí

## 1. Objetivo

Definir cómo Cyrvanta transforma una recomendación de respuesta en una
decisión humana o determinística verificable, sin permitir que la IA, el
frontend, n8n o un booleano aportado por el cliente autoricen una ejecución.

La etapa debe producir decisiones y aprobaciones tenant-scoped, persistentes,
append-oriented, auditables y vinculadas a una propuesta inmutable. La salida
es una autorización breve que la futura Etapa 7 podrá consumir, pero esta etapa
no ejecuta workflows ni acciones externas.

## 2. Alcance

Incluye:

- propuesta de acción con parámetros normalizados y fingerprint;
- evaluación determinística de política;
- clasificación de impacto y modalidad requerida;
- aprobación simple o doble;
- separación entre solicitante y aprobadores;
- rechazo, expiración y revocación;
- autorización de ejecución ligada a inputs exactos;
- kill switches global y tenant;
- permisos, RLS, auditoría, API, eventos, i18n y pruebas;
- compatibilidad controlada con la automatización demo existente.

No incluye:

- ejecución o callback n8n;
- importación de workflows;
- conectores de contención reales;
- ejecución automática en producción;
- comandos genéricos, shell, SSH o código generado;
- aprendizaje autónomo de políticas;
- MFA o step-up completos, salvo registrar su futura condición;
- aprobación de una definición de playbook, que pertenecerá al contrato de
  playbooks versionados de Etapa 7.

## 3. Dependencias y fuentes

Esta propuesta depende de:

- D-007, D-008 y D-009 del plan de diferenciadores;
- `docs/domain/AUTHORIZATION_MODEL.md`;
- `docs/domain/DOMAIN_MODEL.md`;
- `docs/specifications/PHASE_15_EVENT_DELIVERY_TRACEABILITY.md`;
- `docs/specifications/PHASE_17_CLAIM_LEDGER.md`;
- `docs/specifications/PHASE_19_MITRE_RISK_EXPLAINABILITY.md`;
- `docs/requirements/N8N_WORKFLOWS_AS_CODE_REQUIREMENTS.md`;
- ADR 0002 para RLS y ADR 0013 para riesgo explicable.

La Etapa 5 ya proporciona riesgo, mappings ATT&CK y explicación. Sus outputs
pueden ser evidencia de una propuesta, pero no autorización.

## 4. Estado actual y brecha

La ruta provisional `POST /api/v1/automations/execute` recibe:

- `incident_id`;
- `workflow_id`;
- `approved: bool`;
- `idempotency_key`.

El backend exige `response.execute`, allowlist y kill switch, pero
`approved: true` no demuestra:

- quién aprobó;
- que el aprobador tenía permiso;
- separación de funciones;
- una segunda aprobación cuando corresponde;
- qué impacto, parámetros y evidencia vio;
- vigencia, revocación o expiración;
- que los inputs actuales coinciden con los aprobados.

La ruta provisional no es una base autorizada para producción. Durante la
implementación de esta etapa deberá quedar deshabilitada para modo `live` hasta
que Etapa 7 consuma autorizaciones persistentes. La demo simulada puede
conservarse temporalmente, rotulada y sin efecto real.

## 5. Principios obligatorios

1. Deny-by-default.
2. El tenant procede exclusivamente del contexto autenticado.
3. La IA recomienda o redacta; nunca decide, aprueba ni autoriza.
4. n8n notifica o ejecuta en Etapa 7; nunca conserva la decisión autoritativa.
5. Toda evaluación usa versiones e inputs explícitos.
6. Toda decisión es append-oriented; una corrección crea un nuevo registro.
7. La autorización queda inválida si cambia cualquier input material.
8. La evaluación se repite inmediatamente antes del dispatch futuro.
9. El kill switch se evalúa al proponer, autorizar y ejecutar.
10. Ninguna modalidad automática se habilita por defecto.

## 6. Lenguaje de dominio candidato

### 6.1 Propuesta de acción

Solicitud inmutable y tenant-owned para considerar una respuesta. Referencia:

- incidente y snapshot de su versión;
- playbook y versión candidata;
- tipo de acción allowlisted;
- modo solicitado;
- targets normalizados;
- parámetros tipados y redactados;
- riesgo e impacto de acción;
- evidencia, recomendación o decisión que la originó;
- actor solicitante;
- correlation y causation IDs;
- fingerprint de todos los inputs materiales.

Crear una propuesta no concede permiso para ejecutarla.

### 6.2 Evaluación de política

Resultado determinístico y versionado que indica:

- `DENIED`;
- `APPROVAL_REQUIRED`;
- `DUAL_APPROVAL_REQUIRED`;
- `ELIGIBLE_FOR_AUTOMATIC`.

`ELIGIBLE_FOR_AUTOMATIC` no significa ejecutado ni habilitado. Requiere una
política tenant explícita, acción allowlisted de bajo impacto y Etapa 7.

La evaluación conserva factores, reglas, versiones y razones codificadas. No
depende de texto generado por IA.

### 6.3 Solicitud de aprobación

Objeto tenant-owned que presenta una propuesta y su evaluación a actores
autorizados. Define cantidad de aprobaciones, separación de funciones,
expiración y estado agregado.

### 6.4 Decisión de aprobación

Registro append-only de un actor:

- `APPROVE`;
- `REJECT`;

con instante, motivo acotado, proposal fingerprint, versión esperada, actor,
tenant, método de autenticación y contexto de seguridad autorizado.

No se permite editar ni borrar una decisión. Revocar o corregir crea un hecho
posterior.

### 6.5 Autorización

Capacidad breve, de un solo propósito, generada solo cuando:

- la política vigente lo permite;
- se alcanzó el quorum;
- se cumple separación de funciones;
- ninguna decisión vigente es rechazo;
- propuesta, versiones e inputs conservan el fingerprint;
- no expiró;
- kill switches están inactivos.

No contiene secretos. Etapa 7 deberá consumirla de forma atómica e
idempotente.

## 7. Clasificación de impacto candidata

Se propone:

| Impacto | Ejemplos iniciales | Modalidad mínima |
|---|---|---|
| `OBSERVATIONAL` | notificar, generar informe, crear ticket | aprobación simple configurable |
| `LOW` | enriquecer o etiquetar en sistema externo | aprobación simple |
| `MODERATE` | revocar sesión de laboratorio, cambio reversible acotado | aprobación simple con solicitante distinto |
| `HIGH` | bloquear usuario, aislar activo, modificar control preventivo | doble aprobación |
| `CRITICAL` | acción masiva, irreversible o sobre infraestructura crítica | denegada en demo/MVP inicial |

La lista exacta action type × impacto debe ser allowlisted y versionada. Un
tenant puede exigir controles más estrictos, nunca relajarlos por debajo del
mínimo de plataforma.

`simulate-user-block` permanece `MODERATE` por semántica, pero su ejecutor demo
no produce efecto real. El rótulo `demo` no elimina la necesidad de trazabilidad.

## 8. Modos de respuesta candidatos

- `RECOMMENDATION_ONLY`: no crea autorización.
- `HUMAN_APPROVAL`: exige un aprobador distinto del solicitante cuando la acción
  es `MODERATE` o superior.
- `DUAL_APPROVAL`: exige dos aprobadores humanos distintos entre sí y del
  solicitante.
- `AUTOMATIC`: solo candidato para acciones `OBSERVATIONAL` o `LOW`, desactivado
  por defecto y fuera de la habilitación inicial.

Una política puede elevar `OBSERVATIONAL` a aprobación simple o exigir doble
aprobación a una acción `MODERATE`.

## 9. Separación de funciones candidata

1. El solicitante no cuenta como aprobador de `MODERATE`, `HIGH` o `CRITICAL`.
2. En doble aprobación, los dos aprobadores son usuarios internos distintos.
3. Una service identity no aprueba.
4. La IA y n8n no son actores aprobadores.
5. `response.request`, `response.approve` y `response.authorize` son permisos
   distintos.
6. `response.execute` se conserva para Etapa 7 y no implica aprobar.
7. Gestionar roles, playbooks o integraciones no concede aprobación.
8. El usuario debe permanecer activo, miembro del tenant y autorizado al
   instante de decidir y al emitir autorización.
9. La cuenta demo tenant-admin puede ejercitar todo el flujo únicamente en
   modo sintético; la UI debe mostrar esta excepción de laboratorio.

## 10. Política determinística candidata

La evaluación considera como mínimo:

- tenant y estado del tenant;
- política y versión;
- action type e impacto;
- modo solicitado;
- playbook/version allowlisted;
- incidente, estado y versión;
- riesgo vigente y definición de riesgo;
- targets y parámetros;
- estado de integraciones requerido;
- kill switches;
- ventana temporal;
- permisos y estado de actores;
- clasificación demo/live;
- restricciones de alcance y cantidad.

La ausencia o desactualización de un input requerido produce `DENIED`; nunca se
rellena con una inferencia.

## 11. Rechazo, expiración y revocación candidatos

- Un rechazo cierra la solicitud de aprobación y evita autorización.
- Una solicitud expira al vencer su ventana.
- Una autorización expira antes que la solicitud que la originó.
- Revocar invalida autorizaciones no consumidas.
- Suspender tenant, usuario, playbook, integración o activar kill switch
  invalida el uso futuro.
- Cambiar parámetros, targets, playbook/version, impacto, incidente/version o
  policy version exige una propuesta nueva.
- No se reutilizan aprobaciones entre propuestas aunque el texto visible sea
  igual.

## 12. Ventanas y límites candidatos

Paquete recomendado para aprobación:

- vigencia de solicitud: 30 minutos;
- vigencia de autorización: 5 minutos;
- máximo de decisiones por solicitud: 8;
- máximo de targets: 100 para `OBSERVATIONAL`, 10 para `LOW`, 1 para
  `MODERATE` y `HIGH`;
- motivo humano: 1 a 1.000 caracteres;
- parámetros normalizados: máximo 32 KiB;
- referencias de evidencia: máximo 32;
- una solicitud abierta por tenant + proposal fingerprint;
- una autorización activa por solicitud;
- tiempos configurables solo dentro de máximos de plataforma.

Exceder límites falla cerrado.

## 13. Modelo lógico candidato

La implementación futura requiere conceptos persistentes separados para:

- definiciones versionadas de política;
- propuestas de acción;
- evaluaciones de política append-only;
- solicitudes de aprobación;
- decisiones append-only;
- autorizaciones de uso único;
- invalidaciones y revocaciones.

Todos los datos operativos incluyen `tenant_id`, UUID, timestamps UTC y RLS
habilitada y forzada. Las relaciones tenant-owned usan claves compuestas o un
control equivalente que impida referencias cross-tenant.

No se aprueban todavía nombres de tablas, columnas, constraints o índices.

## 14. Invariantes físicas requeridas

La especificación física futura deberá garantizar:

- unicidad idempotente por tenant y fingerprint;
- una decisión efectiva por actor y solicitud;
- actores distintos para doble aprobación;
- autorización ligada al fingerprint y versiones;
- autorización de un solo consumo;
- no actualización ni borrado de decisiones;
- bloqueo de referencias cross-tenant;
- concurrencia segura al completar quorum;
- revocación/consumo mediante compare-and-set o lock equivalente.

Las invariantes que PostgreSQL pueda garantizar no deben quedar solo en código.

## 15. API candidata

Se proponen recursos bajo `/api/v1`, con RFC 7807:

- crear y consultar propuestas;
- evaluar o reevaluar política;
- crear y consultar solicitudes de aprobación;
- aprobar o rechazar una solicitud;
- revocar una solicitud o autorización;
- consultar autorización y estado;
- listar de forma paginada y filtrada.

Todos los comandos mutantes requieren `Idempotency-Key` y versión esperada.
Los IDs ajenos al tenant responden `404`.

No se aprueban paths, DTO, status codes específicos ni códigos de error hasta
aprobar este documento.

El cliente nunca envía `tenant_id`, `approved: true`, actor aprobador ni estado
calculado como autoridad.

## 16. Eventos candidatos

- `security.action_proposal.created` v1;
- `security.policy_evaluation.completed` v1;
- `security.approval.requested` v1;
- `security.approval.decided` v1;
- `security.authorization.issued` v1;
- `security.authorization.revoked` v1;
- `security.authorization.expired` v1.

Usan el envelope de Fase 15, outbox/inbox e idempotencia. Los payloads contienen
IDs, versiones, fingerprints y códigos; no incluyen evidencia raw, parámetros
sensibles, motivos completos ni secretos.

Los nombres y payloads definitivos requieren aprobación.

## 17. Permisos candidatos

- `response.request`;
- `response.policy.evaluate`;
- `response.approve`;
- `response.authorize`;
- `response.revoke`;
- `response.read`;
- `response.execute` reservado para Etapa 7;
- `response.policy.manage` separado de aprobar y ejecutar.

Paquete recomendado:

- analista: solicitar y leer;
- aprobador: leer y aprobar;
- responsable de respuesta: autorizar y revocar;
- tenant-admin demo: todos los permisos tenant-owned solo para escenario
  sintético;
- platform-admin: no recibe acceso implícito a decisiones tenant-owned.

La matriz rol × permiso definitiva continúa como decisión humana separada.

## 18. Auditoría

Se auditan:

- creación y deduplicación de propuesta;
- evaluación y cada factor;
- solicitud, aprobación y rechazo;
- quorum alcanzado o incumplido;
- intento de autoaprobación o actor duplicado;
- emisión, consumo, expiración y revocación;
- denegación por política, límite, versión o kill switch;
- cambio y activación de política;
- acceso/exportación privilegiada.

La auditoría contiene referencias, versiones, fingerprints, actor, tenant,
correlation ID y outcome. No duplica secretos, evidencia raw ni parámetros
sensibles.

## 19. Seguridad y multitenancy

- RLS real y forzada con rol de aplicación.
- Repositorios sin consultas tenant-owned sin scope.
- Tenant y actor derivados del contexto autenticado.
- Resolución por tenant antes de revelar existencia.
- FK tenant-scoped.
- Cache keys, locks y mensajes namespaced por tenant.
- Motivos y labels tratados como texto no confiable.
- Targets y parámetros validados contra schemas y allowlists.
- Autorizaciones almacenadas como referencias/fingerprints; no bearer tokens
  reutilizables expuestos al navegador.
- Rate limiting para propuestas y decisiones.
- Logs redactados.
- CSRF y sesión siguen el contrato de autenticación vigente.
- Autorización backend; ocultar botones no es control.

## 20. Observabilidad

Métricas mínimas:

- propuestas por action type e impacto;
- decisiones aprobadas/rechazadas/expiradas;
- tiempo hasta primera decisión y quorum;
- denegaciones por reason code;
- intentos de separación de funciones inválidos;
- autorizaciones emitidas, revocadas, expiradas y consumidas;
- replays e idempotency hits;
- fallos de RLS y referencias cross-tenant en pruebas, no como etiquetas de
  alta cardinalidad en producción.

No se incluyen tenant, user, incident ni proposal IDs como labels de métricas.

## 21. UI e i18n

La UI futura debe:

- mostrar acción, impacto, alcance, targets, reversibilidad y evidencia;
- distinguir recomendación, propuesta, evaluación, decisión y autorización;
- mostrar solicitante y progreso del quorum;
- impedir visualmente, sin sustituir backend, que el solicitante se apruebe;
- mostrar expiración y motivos de denegación;
- marcar inequívocamente demo/synthetic/live;
- ofrecer alternativa textual accesible;
- usar búsqueda y paginación acotadas;
- funcionar en español e inglés;
- no comunicar que una aprobación equivale a ejecución.

## 22. Pruebas de aceptación

### 22.1 Dominio y política

- mismos inputs y versiones producen el mismo resultado y fingerprint;
- cambiar orden de parámetros normalizados no cambia el fingerprint;
- cambiar cualquier input material lo cambia;
- input requerido ausente deniega;
- impacto mínimo de plataforma no puede reducirse por tenant;
- IA, texto o confidence no autorizan.

### 22.2 Separación de funciones

- solicitante no aprueba su acción `MODERATE` o superior;
- un actor no ocupa dos lugares del quorum;
- service identity, IA y n8n no aprueban;
- usuario suspendido o sin permiso no decide;
- doble aprobación solo completa con dos actores válidos distintos.

### 22.3 Ciclo y concurrencia

- rechazo cierra la solicitud;
- expiración y revocación invalidan autorización;
- dos decisiones concurrentes no duplican quorum ni autorización;
- replay de comandos no duplica efectos;
- una autorización se consume una sola vez;
- cambio de versión invalida autorización.

### 22.4 Aislamiento y seguridad

- Tenant A crea, lee y decide sobre sus recursos;
- Tenant A no lee, decide, cuenta ni infiere recursos de Tenant B;
- FK y RLS rechazan referencias cruzadas;
- IDs ajenos producen `404`;
- cache, locks, jobs y eventos preservan tenant;
- parámetros, targets y motivos hostiles no escapan validación;
- logs y auditoría no filtran secretos.

### 22.5 Compatibilidad

- la demo simulada continúa sin efecto real;
- `approved: bool` no habilita modo live;
- análisis, correlación, riesgo y claims no sufren regresiones;
- UI y API existentes conservan comportamiento durante la ventana documentada.

## 23. Migración candidata

Después de aprobar:

1. agregar modelos y RLS mediante una migración nueva;
2. sembrar catálogo de permisos y política demo versionada;
3. implementar dominio y repositorios;
4. publicar API/eventos detrás de una configuración segura;
5. adaptar la UI a propuesta → aprobación → autorización;
6. mantener la ejecución demo provisional únicamente en modo simulado;
7. bloquear modo live de la ruta basada en `approved: bool`;
8. retirar el booleano en una versión API documentada;
9. habilitar Etapa 7 solo después de sus contratos y pruebas.

No se fabrican aprobaciones históricas para ejecuciones anteriores.

## 24. Rollback

- Deshabilitar creación de propuestas no afecta ingesta, correlación, claims,
  riesgo ni lectura de incidentes.
- Revocar autorizaciones activas antes de desactivar la etapa.
- Conservar decisiones y auditoría append-only.
- Mantener la demo simulada anterior solo si sigue claramente rotulada.
- El downgrade físico se bloquea si existen decisiones o autorizaciones hasta
  exportación y remoción administrativa explícita.
- No se borra historia automáticamente.

## 25. Dependencia downstream con Etapa 7 y n8n

Etapa 7 recibirá únicamente:

- ID de autorización;
- proposal fingerprint;
- tenant, incident, playbook y version IDs;
- action type y modo;
- correlation y causation IDs;
- parámetros ya validados mediante referencia o snapshot autorizado;
- expiración y estado de kill switches reevaluado.

`request-dual-approval` puede notificar y ofrecer un enlace a Cyrvanta, pero:

- n8n no decide;
- n8n no guarda quorum;
- el callback n8n no crea aprobaciones;
- la decisión ocurre en el backend de Cyrvanta;
- el workflow no recibe secretos ni evidencia completa.

## 26. Resolución de decisiones materiales

La instrucción humana del 2026-07-29 aprobó sin enmiendas:

1. lenguaje de propuesta, evaluación, solicitud, decisión y autorización;
2. clasificación de cinco impactos;
3. modalidad mínima por impacto;
4. separación solicitante/aprobador;
5. dos aprobadores distintos para `HIGH`;
6. denegación inicial de `CRITICAL`;
7. límites de acciones automáticas;
8. ventanas de 30 y 5 minutos;
9. límites de targets, parámetros, decisiones y evidencia;
10. invalidación por cambios materiales;
11. autorización de un solo uso;
12. política y reason codes versionados;
13. catálogo de permisos;
14. ownership tenant de todos los recursos operativos;
15. API y eventos candidatos;
16. comportamiento del rechazo;
17. revocación y expiración;
18. compatibilidad y retiro de `approved: bool`;
19. excepción del tenant-admin demo;
20. criterios de aceptación, migración y rollback.

## 27. Resolución del paquete recomendado

Las decisiones de las secciones 6 a 25 fueron aprobadas sin variaciones. La
aprobación autorizó:

- registrar el ADR de Etapa 6;
- fijar modelos físicos, constraints e índices;
- crear la migración con RLS;
- formalizar DTO, rutas, errores y eventos;
- implementar política, aprobación y autorización;
- agregar UI bilingüe;
- reemplazar la confianza provisional en `approved: bool`;
- ejecutar las pruebas de aceptación.

No se autorizaron workflows n8n ni acciones reales.

## 28. Criterios de salida

La Etapa 6 estará completa cuando:

1. una propuesta inmutable se evalúe determinísticamente;
2. una acción `HIGH` exija dos aprobadores válidos y distintos;
3. el solicitante no pueda autoaprobarse;
4. cambios materiales invaliden la autorización;
5. rechazo, expiración, revocación y kill switch fallen cerrado;
6. decisiones y autorizaciones sean tenant-scoped, append-oriented y auditadas;
7. RLS y pruebas cross-tenant reales pasen;
8. la demo sintética funcione sin presentar ejecución real;
9. `approved: bool` no pueda autorizar modo live;
10. documentación, ADR, migración, API, eventos, UI, i18n y rollback estén
    actualizados.

## 29. Registro de implementación y validación

La Etapa 6 se implementó el 2026-07-29 con:

- modelos separados para política, propuesta, evaluación, solicitud, decisión y
  autorización;
- política determinística versionada, fingerprints canónicos y límites físicos;
- separación obligatoria entre solicitante y aprobadores;
- autorización breve, revocable y preparada para consumo único en Etapa 7;
- seis tablas tenant-scoped con RLS habilitado y forzado;
- permisos explícitos, auditoría y eventos de dominio;
- API protegida e idempotente;
- visualización bilingüe en el detalle del incidente;
- bloqueo de `approved: bool` como autorización para automatización `live`.

Validación ejecutada:

- `ruff`, `mypy` y 83 pruebas backend aprobadas;
- lint, formato, 7 pruebas frontend y build de producción aprobados;
- migración Alembic `0015_safe_decision` aplicada en PostgreSQL;
- seis políticas RLS verificadas con `FORCE ROW LEVEL SECURITY`;
- prueba transaccional cross-tenant con cero filas ajenas visibles y rollback;
- propuesta sintética creada desde la UI y mostrada como
  `AWAITING_APPROVAL`, sin ejecutar acciones externas.

Los workflows, callbacks y consumo efectivo de la autorización permanecen
fuera de alcance hasta que la especificación de Etapa 7 sea aprobada.

Corrección de trazabilidad del 2026-07-29:

- se normalizaron `action_proposal` y `policy_evaluation` con guion bajo para
  cumplir el patrón vinculante de `EventEnvelopeV1`;
- se completó la emisión transaccional de
  `security.policy_evaluation.completed`,
  `security.approval.requested`, `security.authorization.issued` y
  `security.authorization.revoked`;
- `security.authorization.expired` queda reservado para el proceso durable de
  expiración de Etapa 7; `expires_at` continúa invalidando sincrónicamente el
  uso de la autorización y el modo `live` permanece bloqueado.
