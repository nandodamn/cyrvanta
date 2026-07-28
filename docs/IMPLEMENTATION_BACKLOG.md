# Backlog de implementación

**Estado:** DRAFT. Los ítems `GATE` bloquean diseño físico o código.

## Diferenciadores estratégicos

- [x] Auditar capacidades contra el flujo real.
- [x] Ordenar implementación por dependencias.
- [x] GATE: aprobar D-001 a D-012 del plan estratégico.
- [x] Especificar envelope, outbox/inbox e idempotencia.
- [x] GATE: aprobar `PHASE_15_EVENT_DELIVERY_TRACEABILITY.md`.
- [x] Implementar Etapa 1.
- [x] Especificar Etapa 2 — modelo canónico y procedencia.
- [ ] GATE: aprobar
  `PHASE_16_CANONICAL_SECURITY_MODEL_PROVENANCE.md`.
- [ ] Fijar límites físicos, retención, calidad, severidad y redacción con
  muestras representativas antes de implementar Etapa 2.
- [ ] Implementar Etapa 2 solo después de aprobar su contrato y pendientes
  físicos.

## Gobernanza

- [ ] GATE: revisión humana de todos los documentos de Fase 0 y Fase 1.
- [ ] GATE: incorporar la consulta/requisitos oficiales de AGESIC con versión y
  trazabilidad.
- [x] Verificar o inicializar Git y configurar el remoto autorizado.
- [ ] Aprobar licencia, política de contribución y responsables.
- [ ] Fijar versiones de Python, Node, PostgreSQL, OpenSearch y demás imágenes.
- [ ] Decidir herramientas exactas de paquetes, tipado, proxy y secretos.
- [ ] Actualizar React Router cuando exista una versión sin los advisories
  documentados en ADR 0006 y repetir pruebas de navegación/redirect.

## Dominio

- [ ] GATE: aprobar glosario y terminología bilingüe.
- [x] GATE: usuarios multi-tenant mediante membresía explícita (D-001);
  contrato físico pendiente.
- [ ] GATE: aprobar ciclo de vida de incidentes y reglas de concurrencia.
- [ ] GATE: aprobar identidad local/LDAP y resolución de colisiones.
- [ ] GATE: aprobar modelo RBAC y alcance del administrador de plataforma.
- [ ] GATE: aprobar evidencia, cadena de custodia, auditoría y retención.
- [ ] Definir reglas de correlación, riesgo, confianza y versionado.
- [ ] Definir modos de respuesta y clasificación de impacto.

## Datos y contratos — no iniciar antes de los GATE

- [ ] Crear modelo lógico y ERD sin asumir nombres físicos prematuramente.
- [ ] Diseñar RLS y pruebas negativas.
- [ ] Diseñar retención, borrado y backup/restore.
- [ ] Aprobar catálogo físico y primera migración Alembic.
- [ ] Publicar OpenAPI 3.1 y RFC 7807.
- [ ] Publicar envelopes y eventos RabbitMQ.
- [ ] Publicar schemas de IA y contratos Wazuh/OpenSearch/n8n.

## Implementación

- [ ] Bootstrap reproducible de backend, frontend, Compose y CI.
- [ ] Implementar fases 5–18 según `docs/ROADMAP.md`.
- [ ] Mantener pruebas unitarias, componentes, contratos, API, RLS,
  cross-tenant, seguridad, frontend y E2E en cada incremento.
