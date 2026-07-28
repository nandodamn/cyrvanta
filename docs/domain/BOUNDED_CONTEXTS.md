# Bounded Contexts

**Estado:** DRAFT — propuesta para revisión humana; no define contratos.

## Principios de relación

Cada contexto posee su lenguaje, reglas y modelo. La integración ocurre por
casos de uso, puertos o eventos candidatos que deberán especificarse y
versionarse en Fase 3. Un contexto no importa repositorios ni modelos de
infraestructura de otro. El tenant y la identidad actuante acompañan toda
operación tenant-owned.

| Contexto | Responsabilidad | Datos conceptualmente propios | Dependencias permitidas |
|---|---|---|---|
| Identity and Access | Autenticación, identidades, roles y permisos | User, Identity, Role, Permission | Tenant Administration; Audit mediante puerto |
| Tenant Administration | Tenant, configuración y políticas | Tenant, TenantSettings | Identity para actor; Audit |
| Security Integrations | Configuración, capacidades, sincronización, salud y normalización de conectores reemplazables | Integration, estado de sincronización y salud | Tenant; adaptadores externos |
| Telemetry and Alert Intake | Referencias canónicas de hallazgos y alertas | AlertReference; modelos canónicos transitorios | Security Integrations mediante puerto |
| Incident Management | Ciclo, asignación, evidencia y timeline | Incident, IncidentEvidence, IncidentTimelineEntry | Intake; Identity; Audit |
| Correlation | Candidatos, agrupación y explicación | Decisiones/versiones de correlación por especificar | Intake; Incident; Risk |
| Threat Knowledge | Catálogo ATT&CK y mappings versionados | MITREMapping y catálogo global | Incident; fuente STIX por puerto |
| AI Analysis | Solicitudes, resultados y provenance | AIAnalysis | Incident; Threat Knowledge; `AIProvider` |
| Risk and Policy | Evaluación determinística y elegibilidad | RiskAssessment | Incident; AI como señal; Tenant policy |
| Playbook and Response | Definiciones, aprobaciones y ejecución | Playbook, PlaybookVersion, Approval, PlaybookExecution | Risk; Identity; automation port |
| Audit and Compliance | Registro append-oriented y consulta autorizada | AuditEvent | Recibe hechos de todos; no controla su negocio |
| Reporting and Analytics | Métricas y vistas autorizadas | Proyecciones/reportes por especificar | Puertos de lectura acotados |
| Platform Operations | Salud, versiones, jobs y operación | Estado operacional por especificar | Adaptadores de infraestructura |

## Flujos principales propuestos

1. **Ingreso:** integración → normalización → referencia de alerta → candidato
   de correlación.
2. **Incidente:** correlación explicada → creación/actualización de incidente →
   evidencia referenciada → timeline/auditoría.
3. **Análisis:** incidente autorizado → evidencia minimizada → contexto ATT&CK
   → IA validada → riesgo determinístico.
4. **Respuesta:** recomendación → política → aprobación cuando corresponda →
   adaptador de automatización → resultado y auditoría.
5. **Identidad:** proveedor local/LDAP → identidad interna → contexto tenant →
   permisos → caso de uso.

## Reglas de ownership

- El catálogo ATT&CK base es global; un mapping a incidente es tenant-owned.
- Configuración, credenciales metadata, incidentes, análisis, respuestas y
  auditoría operativa son tenant-owned salvo estado explícitamente global.
- La telemetría permanece en OpenSearch; el dominio conserva referencias y
  evidencia seleccionada.
- Reporting consume proyecciones; no modifica agregados de otros contextos.
- Audit registra hechos pero no se usa como sustituto de datos de negocio.

## Preguntas bloqueantes

- ¿Puede una persona/usuario pertenecer a varios tenants?
- ¿Qué operaciones cross-tenant posee un administrador de plataforma?
- ¿Qué datos de Threat Knowledge puede personalizar un tenant?
- ¿Correlation crea incidentes o propone comandos a Incident Management?
- ¿Qué consistencia se exige entre PostgreSQL, OpenSearch y RabbitMQ?
- ¿Qué eventos son de dominio internos y cuáles son contratos de integración?
