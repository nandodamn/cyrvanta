# Modelo de dominio conceptual

**Estado:** DRAFT — propuesta para revisión humana.  
**Prohibición:** este documento no aprueba tablas, columnas, DTO, endpoints ni
eventos de integración.

## Convenciones

- Los atributos son conceptos de negocio, no nombres físicos.
- `tenant-owned` exige tenant derivado del contexto autenticado y aislamiento
  en todas las capas. `global` no significa acceso público.
- Los comandos y eventos listados son candidatos; deberán formalizarse en
  especificaciones posteriores.
- Todos los instantes son UTC y los identificadores de recursos serán UUID salvo
  excepción aprobada.
- Las operaciones mutantes y de seguridad son auditables.
- Datos sensibles se minimizan, clasifican, cifran o redactan según política.
- Las decisiones de IA no sustituyen autorización, política ni validación.

## Agregados candidatos

La siguiente agrupación orienta consistencia, pero no está aprobada:

- Tenant: `Tenant` y `TenantSettings`.
- Identity: `User`, `Identity`, `Role`, `Permission`.
- Integration: `Integration`.
- Asset inventory: `Asset`.
- Incident: `Incident`, `IncidentEvidence`, `IncidentTimelineEntry`.
- Threat mapping: `MITREMapping`.
- AI analysis: `AIAnalysis`.
- Risk: `RiskAssessment`.
- Playbook definition: `Playbook`, `PlaybookVersion`.
- Execution: `Approval`, `PlaybookExecution`.
- Audit: `AuditEvent`.

## Entidades y conceptos

### Tenant

- **Propósito/ownership:** límite organizacional de aislamiento; es raíz de
  tenant y su registro es de plataforma.
- **Atributos conceptuales:** identidad, nombre visible, estado, locale/timezone
  predeterminados y referencias de política. No se fijan campos físicos.
- **Invariantes/ciclo:** identidad estable; creación, activación, suspensión y
  retiro controlados; suspender no elimina datos ni rompe auditoría.
- **Comandos/eventos candidatos:** provisionar, activar, suspender, retirar;
  `TenantProvisioned`, `TenantStatusChanged`.
- **Relaciones/permisos:** contiene configuración y recursos; `tenant.manage`;
  provisión global requiere operación de plataforma explícita.
- **Sensibilidad/auditoría:** datos organizacionales y estado; auditar toda
  mutación y acceso administrativo cross-tenant.

### TenantSettings

- **Propósito/ownership:** preferencias y políticas configurables de un tenant;
  tenant-owned.
- **Atributos conceptuales:** locales, timezone, retención, IA, respuesta,
  features e integración de identidad como referencias versionadas.
- **Invariantes/ciclo:** defaults seguros; automático desactivado; cambios
  validados, versionados y con vigencia conocida.
- **Comandos/eventos candidatos:** actualizar preferencia/política;
  `TenantSettingsChanged`.
- **Relaciones/permisos:** pertenece a Tenant; `tenant.manage`; políticas de
  alto impacto pueden exigir aprobación adicional.
- **Sensibilidad/auditoría:** configuración de seguridad; no contiene secretos
  en claro; registrar antes/después redactado y actor.

### User

- **Propósito/ownership:** persona o cuenta interna que puede actuar en la
  plataforma; alcance de ownership pendiente por usuarios multi-tenant.
- **Atributos conceptuales:** identidad visible, estado, preferencias, locale,
  timezone y asociaciones autorizadas.
- **Invariantes/ciclo:** no autentica por sí mismo; alta/invitación, activación,
  suspensión y retiro; deshabilitar corta acceso conforme a política.
- **Comandos/eventos candidatos:** crear/invitar, activar, suspender, actualizar;
  `UserCreated`, `UserStatusChanged`.
- **Relaciones/permisos:** posee Identity y asignaciones de Role; gestión
  requiere permiso administrativo por definir.
- **Sensibilidad/auditoría:** PII; minimizar exposición y auditar cambios,
  asignaciones y accesos privilegiados.

### Identity

- **Propósito/ownership:** vínculo verificable entre un proveedor de
  autenticación y un User; tenant-scoped cuando el proveedor lo sea.
- **Atributos conceptuales:** tipo local/LDAP, identificador externo estable,
  estado, timestamps de vinculación y autenticación; nunca password LDAP.
- **Invariantes/ciclo:** combinación proveedor/sujeto no se vincula
  ambiguamente; vincular, verificar, deshabilitar y desvincular con protección
  contra lockout.
- **Comandos/eventos candidatos:** vincular, verificar, deshabilitar;
  `IdentityLinked`, `IdentityDisabled`, `AuthenticationSucceeded/Failed`.
- **Relaciones/permisos:** pertenece a User y proveedor/configuración; gestión
  administrativa explícita.
- **Sensibilidad/auditoría:** identificadores y señales de login; credenciales
  separadas/cifradas; fallos auditados sin secretos.

### Role

- **Propósito/ownership:** agrupación administrable de permisos; puede ser
  global predeterminado o tenant-owned, decisión pendiente.
- **Atributos conceptuales:** nombre/código estable, descripción, estado,
  origen y conjunto de permisos.
- **Invariantes/ciclo:** no concede permisos inexistentes; cambios no deben
  autoescalar al editor; crear, modificar, desactivar.
- **Comandos/eventos candidatos:** crear rol, conceder/revocar permiso,
  desactivar; `RoleChanged`.
- **Relaciones/permisos:** contiene Permission y se asigna a User en un tenant;
  `tenant.manage` o permiso específico pendiente.
- **Sensibilidad/auditoría:** configuración de autorización; toda asignación y
  cambio se audita con separación de funciones.

### Permission

- **Propósito/ownership:** capacidad atómica estable evaluada por backend;
  catálogo global administrado por versión del producto.
- **Atributos conceptuales:** código, recurso, acción, descripción y estado.
- **Invariantes/ciclo:** código único y semántica no cambia silenciosamente;
  introducción/deprecación mediante versión.
- **Comandos/eventos candidatos:** registrar/deprecar por release;
  `PermissionCatalogChanged`.
- **Relaciones/permisos:** integra Role; no se concede directamente salvo
  decisión formal.
- **Sensibilidad/auditoría:** no sensible, pero crítica para seguridad; cambios
  de catálogo y grants son auditables.

### Integration

- **Propósito/ownership:** configuración lógica de un sistema externo;
  tenant-owned.
- **Atributos conceptuales:** tipo, nombre, estado, capacidades, endpoint
  validado, referencia a secreto, política de sincronización y salud.
- **Invariantes/ciclo:** adaptador soportado; secretos fuera del modelo visible;
  crear, probar, activar, degradar, desactivar, retirar.
- **Comandos/eventos candidatos:** configurar, probar, sincronizar, rotar
  referencia, desactivar; `IntegrationConfigured/HealthChanged`.
- **Relaciones/permisos:** pertenece a Tenant; `integration.read/manage`;
  alimenta Intake o Automation mediante puertos.
- **Sensibilidad/auditoría:** endpoints, usernames y metadata pueden ser
  sensibles; nunca registrar secreto; auditar pruebas y cambios.

### Asset

- **Propósito/ownership:** activo observado o administrado involucrado en
  evidencia/incidentes; tenant-owned.
- **Atributos conceptuales:** identidad canónica, identificadores observados,
  tipo, criticidad, estado, etiquetas y procedencia.
- **Invariantes/ciclo:** deduplicación explicable; no fusionar activos entre
  tenants; observado, confirmado, actualizado, fusionado o retirado.
- **Comandos/eventos candidatos:** registrar observación, confirmar, clasificar,
  fusionar; `AssetObserved`, `AssetCriticalityChanged`.
- **Relaciones/permisos:** relacionado con alertas/incidentes/riesgo; permisos
  de inventario aún no definidos.
- **Sensibilidad/auditoría:** hostname, IP, propietario y topología son
  sensibles; auditar criticidad y fusiones.

### AlertReference

- **Propósito/ownership:** referencia normalizada a una alerta conservada en la
  fuente/OpenSearch; tenant-owned.
- **Atributos conceptuales:** fuente e ID externo, timestamp, severidad,
  clasificación, entidades resumidas, referencia raw, hash y provenance.
- **Invariantes/ciclo:** fuente+ID+tenant es idempotente conceptualmente; la
  referencia no confiere acceso raw; ingresada, actualizada o expirada.
- **Comandos/eventos candidatos:** registrar/actualizar referencia, promover;
  `AlertReferenced`, `AlertPromoted`.
- **Relaciones/permisos:** puede relacionarse con incidentes y assets;
  `alert.read`, creación normalmente por integración.
- **Sensibilidad/auditoría:** metadata de seguridad; minimizar snapshots;
  registrar acceso a evidencia según política.

### Incident

- **Propósito/ownership:** unidad coordinada de investigación y respuesta;
  tenant-owned y agregado central.
- **Atributos conceptuales:** título, estado, severidad, clasificación,
  prioridad, responsable/equipo, SLA, etiquetas y versión.
- **Invariantes/ciclo:** ver `INCIDENT_LIFECYCLE.md`; transiciones válidas,
  concurrencia optimista, explicación y tenant inmutables.
- **Comandos/eventos candidatos:** crear, triage, asignar, actualizar, cerrar,
  reabrir, relacionar/fusionar; eventos de ciclo allí definidos.
- **Relaciones/permisos:** alertas, assets, evidencia, mappings, análisis,
  riesgo y ejecuciones; permisos `incident.*`.
- **Sensibilidad/auditoría:** datos operativos altamente sensibles; cada
  mutación, acceso privilegiado y exportación se audita.

### IncidentEvidence

- **Propósito/ownership:** evidencia seleccionada o referencia preservada que
  sustenta decisiones; tenant-owned bajo Incident.
- **Atributos conceptuales:** tipo, referencia de origen, snapshot mínimo,
  hash, timestamps, provenance, clasificación y política de retención.
- **Invariantes/ciclo:** no cambia silenciosamente; integridad verificable;
  captura, validación, supersesión/expiración sin borrar historial indebido.
- **Comandos/eventos candidatos:** adjuntar, validar integridad, clasificar,
  restringir; `EvidenceLinked`, `EvidenceIntegrityChecked`.
- **Relaciones/permisos:** pertenece a Incident y puede sustentar mapping,
  análisis y riesgo; lectura exige acceso al incidente y a su clasificación.
- **Sensibilidad/auditoría:** puede contener PII, secretos o payload hostil;
  redacción, acceso y exportación reforzados.

### IncidentTimelineEntry

- **Propósito/ownership:** hecho cronológico visible de la investigación;
  tenant-owned y append-oriented.
- **Atributos conceptuales:** tipo, instante efectivo/registrado, actor o
  proceso, resumen localizado y referencia al hecho origen.
- **Invariantes/ciclo:** no reordenar ni editar hechos silenciosamente;
  correcciones crean nueva entrada; creado y eventualmente redactado por regla.
- **Comandos/eventos candidatos:** añadir/anotar/corregir;
  `TimelineEntryAdded`.
- **Relaciones/permisos:** pertenece a Incident; lectura según incidente,
  escritura según tipo de comando.
- **Sensibilidad/auditoría:** texto puede ser sensible; entrada y redacción
  quedan auditadas.

### MITREMapping

- **Propósito/ownership:** afirmación versionada entre evidencia de incidente y
  objeto ATT&CK; tenant-owned aunque catálogo sea global.
- **Atributos conceptuales:** ID ATT&CK, versión de dataset, evidencia, origen
  humano/regla/modelo, confianza, razón bilingüe y validación humana.
- **Invariantes/ciclo:** ID debe existir en versión indicada; evidencia
  accesible al mismo tenant; propuesto, validado, rechazado o supersedido.
- **Comandos/eventos candidatos:** proponer, validar, rechazar, superseder;
  `MITREMappingProposed/Validated`.
- **Relaciones/permisos:** Incident, Evidence y catálogo; lectura `mitre.read`
  más acceso al incidente; validación requiere permiso pendiente.
- **Sensibilidad/auditoría:** la razón puede revelar evidencia; registrar
  modelo/regla, actor, cambios y versión.

### AIAnalysis

- **Propósito/ownership:** solicitud y resultado validado de una capacidad IA;
  tenant-owned.
- **Atributos conceptuales:** tipo, estado, proveedor/modelo, prompt version,
  parámetros, evidencia, salida estructurada, errores, latencia y uso.
- **Invariantes/ciclo:** contexto tenant autorizado y minimizado; schema
  estricto; solicitado, en proceso, completado, fallido/cancelado; resultado no
  autoriza acciones.
- **Comandos/eventos candidatos:** solicitar, iniciar, completar, fallar,
  cancelar, aportar feedback; `AIAnalysisRequested/Validated/Failed`.
- **Relaciones/permisos:** Incident/Evidence/MITRE y `AIProvider`;
  `analysis.request/read`.
- **Sensibilidad/auditoría:** prompts/evidencia pueden ser sensibles y hostiles;
  retención/redacción, provenance y acceso auditados.

### RiskAssessment

- **Propósito/ownership:** evaluación determinística, versionada y explicable de
  riesgo; tenant-owned.
- **Atributos conceptuales:** score, categoría, factores, pesos, modelo/regla,
  evidencia, instante y explicación.
- **Invariantes/ciclo:** IA solo aporta señales; mismos inputs/version producen
  resultado reproducible; calculado y posteriormente supersedido, no
  reescrito.
- **Comandos/eventos candidatos:** calcular/recalcular;
  `RiskAssessed`, `RiskAssessmentSuperseded`.
- **Relaciones/permisos:** Incident, Asset, Mapping y AIAnalysis como señal;
  lectura sigue permiso de incidente; configuración de modelo separada.
- **Sensibilidad/auditoría:** factores pueden revelar contexto; conservar
  versión, inputs referenciados y actor/proceso.

### Playbook

- **Propósito/ownership:** identidad estable de una respuesta orquestada;
  tenant-owned o catálogo global reutilizable, pendiente de decisión.
- **Atributos conceptuales:** nombre, propósito, estado, clasificación de
  riesgo, propietario y versiones.
- **Invariantes/ciclo:** no ejecutable sin versión aprobada; borrador, activo,
  suspendido y retirado; retiro no borra ejecuciones.
- **Comandos/eventos candidatos:** crear, publicar versión, activar/suspender;
  `PlaybookCreated/StatusChanged`.
- **Relaciones/permisos:** contiene PlaybookVersion; `playbook.read/manage`;
  separación de gestión, aprobación y ejecución.
- **Sensibilidad/auditoría:** puede revelar controles internos; auditar acceso
  privilegiado y cambios.

### PlaybookVersion

- **Propósito/ownership:** definición inmutable y aprobable de parámetros,
  acciones y compensación; sigue ownership del Playbook.
- **Atributos conceptuales:** versión, schema de parámetros, pasos, timeouts,
  retry, riesgo, aprobación, workflow allowlisted y rollback.
- **Invariantes/ciclo:** publicada es inmutable; parámetros tipados; sin shell
  genérico; draft, review, approved, deprecated.
- **Comandos/eventos candidatos:** crear draft, revisar, aprobar, deprecar;
  `PlaybookVersionApproved/Deprecated`.
- **Relaciones/permisos:** ejecutada por PlaybookExecution; gestión
  `playbook.manage`, aprobación de definición por separar.
- **Sensibilidad/auditoría:** referencias a workflows/targets son sensibles;
  secretos solo por referencia; toda revisión se registra.

### Approval

- **Propósito/ownership:** decisión explícita sobre una ejecución o acción;
  tenant-owned.
- **Atributos conceptuales:** objeto solicitado, decisión, actor, instante,
  razón, impacto mostrado y condición/doble control.
- **Invariantes/ciclo:** aprobador autorizado y, cuando aplique, distinto al
  solicitante; pendiente, aprobada, rechazada, expirada o revocada.
- **Comandos/eventos candidatos:** aprobar, rechazar, expirar, revocar;
  `ApprovalGranted/Rejected/Expired`.
- **Relaciones/permisos:** PlaybookExecution, User y política;
  `response.approve`.
- **Sensibilidad/auditoría:** decisión de seguridad; append-oriented, no
  editable y con contexto completo auditado.

### PlaybookExecution

- **Propósito/ownership:** intento controlado de ejecutar una versión de
  playbook contra targets permitidos; tenant-owned.
- **Atributos conceptuales:** versión, parámetros validados, targets,
  modalidad, estado, idempotencia, correlación, resultados y compensación.
- **Invariantes/ciclo:** tenant/target/política/kill switch válidos; solo
  versión aprobada; queued, awaiting approval, running, succeeded, failed,
  cancelled/compensated, sujetos a aprobación.
- **Comandos/eventos candidatos:** solicitar, autorizar, iniciar, registrar
  callback, cancelar, compensar; `ExecutionRequested/Started/Completed/Failed`.
- **Relaciones/permisos:** Incident, Version, Approval y adapter n8n;
  `response.recommend/approve/execute`.
- **Sensibilidad/auditoría:** parámetros/resultados pueden ser sensibles;
  secretos no persistidos en claro; cada transición/callback auditado.

### AuditEvent

- **Propósito/ownership:** registro append-oriented de una acción o decisión de
  seguridad; tenant-owned o global explícito.
- **Atributos conceptuales:** actor/proceso, acción, recurso, tenant, instante,
  resultado, correlación, origen y detalles redactados.
- **Invariantes/ciclo:** append-only lógico, timestamps y correlación
  preservados; creado y retenido/exportado según política; no sustituye
  evidencia de negocio.
- **Comandos/eventos candidatos:** registrar hecho; exportar mediante consulta
  autorizada. No se edita; una corrección es otro evento.
- **Relaciones/permisos:** referencia recursos sin importar sus modelos;
  `audit.read`; escritura solo por puerto interno confiable.
- **Sensibilidad/auditoría:** el propio audit puede ser sensible; acceso al
  audit también se audita; integridad técnica exacta queda pendiente.

## Value Objects candidatos

`TenantContext`, `ActorContext`, `PermissionCode`, `IncidentStatus`,
`Severity`, `Confidence`, `RiskScore`, `TimeRange`, `EvidenceReference`,
`SourceReference`, `CorrelationId`, `IdempotencyKey`, `Locale`,
`ModelReference`, `PromptVersion`, `ATTACKObjectReference`,
`PlaybookVersionReference` y `DataClassification`.

Cada uno necesita semántica, validación y representación aprobadas antes de
implementarse.

## Reglas transversales

1. Un recurso tenant-owned no cambia de tenant.
2. Ningún ID proporcionado demuestra ownership.
3. Los listados, conteos, búsquedas y errores también preservan aislamiento.
4. Los mensajes asíncronos portan tenant/correlación/evento/version y se
   validan antes de uso.
5. Los datos provenientes de telemetría y usuarios son no confiables.
6. El historial de evidencia, ATT&CK, IA, riesgo y respuesta conserva versión y
   provenance.
7. Las eliminaciones, retención y exportaciones requieren especificación legal.

## Brechas que bloquean Fase 2

- Definición legal/operativa de tenant y usuarios multi-tenant.
- Cardinalidades, ownership y límites de cada agregado.
- Estados/transiciones finales y catálogo de motivos.
- Estrategia local/LDAP, vinculación y break-glass.
- Matriz completa de permisos y separación de funciones.
- Definición de evidencia, cadena de custodia y retención.
- Volumen, consultas, SLA, RPO/RTO y concurrencia esperados.
- Estrategia OpenSearch por tenant y consistencia entre almacenes.
- Reglas iniciales de correlación y modelo de riesgo.
- Semántica de auditoría, integridad y requisitos Ley 18.331/GDPR.
- Política de IA, entrenamiento, retención, redacción y egress.
- Catálogo de acciones, impacto, doble control, kill switch y compensación.
