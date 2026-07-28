# Matriz de requisitos AGESIC

**Estado:** DRAFT — trazabilidad preliminar, no evaluación de conformidad.

## Fuente disponible

El solicitante proporcionó el texto denominado `Pasted text(5).txt`,
correspondiente a la Solicitud de Información N.º 02/2026, Inciso 2, Unidad
Ejecutora 10. El archivo se leyó el 2026-07-27. No se incluyó URL, firma, hash ni
copia publicada por ARCE, por lo que su autenticidad y versión deben verificarse
antes de declarar conformidad.

La sección 3 describe capacidades buscadas. La sección 6 solicita información
para una presentación y no convierte por sí sola cada pregunta en una
funcionalidad contractual. Las secciones 4–8 regulan el procedimiento de la
consulta, no el diseño del producto.

Estados: `FUENTE_POR_VERIFICAR`, `POR_ESPECIFICAR`, `POR_IMPLEMENTAR`,
`VERIFICADO`.

| ID provisional | Requisito aportado | Módulo | Funcionalidad | Estado | Evidencia futura | Prueba requerida | Observaciones |
|---|---|---|---|---|---|---|---|
| REQ-001 | Aislamiento multitenant | Todos | Contexto y acceso tenant-scoped | POR_ESPECIFICAR | Diseño RLS, código y logs de CI | Negativas A/B en API, DB, search, cache y jobs | Solicitado en sección 6 como “nivel de aislamiento” y ampliado por Foundation |
| REQ-002 | Autenticación local | Identity and Access | Login, rotación, revocación y lockout | POR_ESPECIFICAR | Especificación y reportes de prueba | Positivas, negativas, abuso y sesión | Requisito Cyrvanta; no aparece explícito en consulta |
| REQ-003 | LDAP/Active Directory | Identity and Access | Login, JIT y grupos a roles | POR_ESPECIFICAR | Contract tests con laboratorio | LDAPS, caída, colisión y no persistencia de password | Requisito Cyrvanta; no aparece explícito en consulta |
| REQ-004 | Autorización deny-by-default | Identity and Access | RBAC y permisos explícitos | POR_ESPECIFICAR | Matriz rol/permiso y auditoría | Cada operación permitida/denegada | Control derivado de seguridad |
| REQ-005 | Auditoría integral | Audit and Compliance | Accesos, cambios, IA y respuesta | POR_ESPECIFICAR | Eventos, retención y exportación | Integridad, orden, acceso y redacción | Consulta solicita observabilidad; alcance Cyrvanta mayor |
| REQ-006 | Operación on-premise | Platform Operations | Despliegue privado | POR_ESPECIFICAR | Compose/runbook/SBOM | Instalación limpia y recuperación | Sección 6 pide modalidad y requisitos de despliegue |
| REQ-007 | Soberanía de datos | Platform Operations | Procesamiento dentro del límite | POR_ESPECIFICAR | Flujo de datos y egress policy | Verificación de red y configuración | Sección 6 pide localización cloud y uso de datos |
| REQ-008 | Datos sensibles protegidos | Shared Security | Secretos, cifrado y redacción | POR_ESPECIFICAR | Threat model y scan reports | Secret scan, logs y acceso | Sección 6: protección de sistema, datos e IA |
| REQ-009 | Integración multifuente | Integration Management | SIEM/EDR/SOAR/NDR/red/aplicaciones | POR_ESPECIFICAR | Contratos y pruebas de adapters | Fixtures, errores y compatibilidad | Secciones 3 y 6 |
| REQ-010 | Búsqueda de telemetría segura | Telemetry Intake | Evidencia y búsqueda acotada | POR_ESPECIFICAR | Query policy y adapter logs | Tenant, allowlist, timeout y límites | Control Cyrvanta para satisfacer ingestión/correlación |
| REQ-011 | Correlación automática y explicable | Correlation | Reglas, estadísticas y apoyo IA | POR_ESPECIFICAR | Versiones y razones persistidas | Reproducibilidad y evaluación | Secciones 3 y 6 |
| REQ-012 | MITRE ATT&CK | Threat Knowledge | Escenarios, catálogo y mappings | POR_ESPECIFICAR | Dataset, import logs y mappings | Validación IDs y actualización | Sección 3 |
| REQ-013 | IA/ML transparente | AI Analysis | Modelos reemplazables y explicabilidad | POR_ESPECIFICAR | Model cards, configuración y tests | Health, schema, timeout y fallback | Sección 6 pide modelos y transparencia |
| REQ-014 | Uso y entrenamiento de datos controlado | AI Analysis | Retención, redacción y no entrenamiento implícito | POR_ESPECIFICAR | Política de datos/modelos | Egress, retención y aislamiento | Sección 6 pregunta alcance de entrenamiento |
| REQ-015 | Priorización y clasificación | Risk and Policy | Score versionado y explicable | POR_ESPECIFICAR | Modelo aprobado y factores | Casos límite y reproducibilidad | Sección 3 |
| REQ-016 | Playbooks parciales o totales | Playbook and Response | Recomendación/aprobación/automático | POR_ESPECIFICAR | Políticas y ejecuciones auditadas | Aprobación, idempotencia y rollback | Secciones 3 y 6 |
| REQ-017 | Detección/reducción de falsos positivos | Correlation | Feedback y evaluación | POR_ESPECIFICAR | Dataset y métricas | Precisión, recall y regresión | Sección 6 |
| REQ-018 | Análisis en lenguaje natural | AI Analysis | Resúmenes e informes | POR_ESPECIFICAR | Schemas y evaluaciones | Fidelidad, evidencia y locales | Secciones 3 y 6 |
| REQ-019 | Investigación y reducción MTTD/MTTR | Incident Management | Asistencia y medición | POR_ESPECIFICAR | Métricas y trazas | Definiciones temporales y E2E | Sección 3 |
| REQ-020 | Observabilidad | Platform Operations | Logs, métricas y health | POR_ESPECIFICAR | Dashboards y runbooks | Correlación y ausencia de secretos | Sección 6 |
| REQ-021 | Escalamiento y volumen | Platform Operations | Capacidad y performance | POR_ESPECIFICAR | Modelo de carga y resultados | Carga, estrés y degradación | Sección 6; cifras no suministradas |
| REQ-022 | Evolución, actualización y soporte | Platform Operations | Roadmap, mantenimiento, SLA y capacitación | POR_ESPECIFICAR | Runbooks y oferta operativa | Actualización/rollback y SLA | Secciones 3 y 6 |
| REQ-023 | Cumplimiento de privacidad | Audit and Compliance | Ley 18.331 y GDPR según aplicabilidad | POR_ESPECIFICAR | Análisis legal aprobado | Derechos, retención y exportación | Sección 6; requiere asesoría jurídica |
| REQ-024 | Inteligencia de amenazas | Threat Knowledge | Enriquecimiento automático | POR_ESPECIFICAR | Contratos de fuentes | Provenance, timeout y datos hostiles | Sección 6 |
| REQ-025 | Informes automatizados | Reporting and Analytics | Reportes operativos/ejecutivos | POR_ESPECIFICAR | Especificación y muestras | Exactitud, permisos e i18n | Sección 6 |
| REQ-026 | Modelo comercial | Platform Operations | Licenciamiento, PoC y dos modalidades | POR_ESPECIFICAR | Propuesta comercial | Revisión humana | Sección 6; fuera del dominio técnico actual |

## Datos requeridos para completar la matriz

1. URL oficial ARCE y copia íntegra/versionada de la consulta.
2. Respuestas oficiales a preguntas y eventuales aclaraciones.
3. Perfil de seguridad y normativa aplicable.
4. Volumen, capacidad, disponibilidad, RPO/RTO y SLA esperados.
5. Criterios de aceptación y evidencia exigida.
6. Requisitos de residencia, retención, auditoría y notificación.
7. Estrategia de soporte, capacitación, licenciamiento y costes.
8. Revisor autorizado para aprobar interpretación y estado.
