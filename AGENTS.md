# Cyrvanta — Reglas obligatorias para agentes

Este archivo aplica a todo el repositorio. Un `AGENTS.md` más específico puede
añadir restricciones, pero no debilitar estas reglas.

## Lectura obligatoria

Antes de crear, modificar, renombrar o eliminar archivos, leer completamente y
en este orden:

1. `docs/foundation/README.md`
2. `docs/foundation/01_PROJECT_VISION.md`
3. `docs/foundation/02_SYSTEM_ARCHITECTURE.md`
4. `docs/foundation/03_DEVELOPMENT_RULES.md`
5. `docs/foundation/04_TECHNOLOGY_STACK.md`
6. `docs/foundation/AI_DEVELOPER_MASTER_PROMPT.md`
7. La especificación aprobada del módulo afectado.
8. Los ADR, contratos, migraciones y pruebas relacionados.

Si existe `Pasted text(5).txt`, leerlo después de Foundation. Su ausencia no
autoriza a inventar requisitos.

## Precedencia

1. Seguridad y aislamiento multitenant.
2. Requisitos AGESIC respaldados por una fuente oficial y aprobados.
3. `docs/foundation/03_DEVELOPMENT_RULES.md`.
4. `docs/foundation/02_SYSTEM_ARCHITECTURE.md`.
5. Especificaciones y ADR posteriores aprobados.
6. Conveniencia técnica.

Ante una contradicción material, detenerse, identificarla y solicitar una
decisión. Nunca cambiar la arquitectura silenciosamente.

## Propiedades no negociables

Cyrvanta es multitenant, bilingüe español/inglés, seguro por defecto,
auditable, modular, desplegable on-premise e independiente de proveedores
mediante puertos y adaptadores. Debe admitir autenticación local y LDAP/Active
Directory. Su stack objetivo incluye React, FastAPI, PostgreSQL, OpenSearch,
Wazuh, RabbitMQ, Redis y n8n. Ollama se configura mediante URL y Gemma 4 es la
familia inicial, nunca un tag hardcodeado.

## Puerta de especificación

No convertir en contrato definitivo, sin especificación formal aprobada:

- entidades, atributos o invariantes del dominio;
- tablas, columnas, relaciones, índices o políticas RLS;
- endpoints, DTO o errores;
- eventos, colas o garantías de entrega;
- permisos o semántica de roles;
- contratos de adaptadores.

Los documentos marcados `DRAFT` son propuestas para revisión, no autorización
de implementación. Si falta una decisión material, registrar la brecha y no
codificarla.

## Límites arquitectónicos

- Monolito modular, Clean Architecture y Ports and Adapters.
- El dominio no depende de FastAPI, SQLAlchemy, RabbitMQ, Redis, OpenSearch,
  Wazuh, Ollama ni n8n.
- El tenant procede del contexto de seguridad autenticado, nunca de un body
  confiado.
- El aislamiento se aplica en servicios, repositorios, PostgreSQL RLS,
  OpenSearch, Redis, mensajes y auditoría.
- PostgreSQL es el sistema de registro funcional y de control; OpenSearch
  conserva telemetría de volumen; Redis no es sistema de registro.
- React no accede directamente a servicios de infraestructura.
- Las tareas largas se procesan de forma asíncrona y conservan tenant,
  correlación e idempotencia.
- La salida de IA es dato no confiable: requiere schema estricto y validación
  determinística. La IA no autoriza ni ejecuta acciones.
- La respuesta automática está desactivada por defecto.
- Toda operación mutante o relevante para seguridad genera auditoría.
- Todo texto de interfaz usa claves i18n en español e inglés.

## Protocolo de cambio

Antes de implementar, informar objetivo, criterios de aceptación, documentos
rectores, archivos afectados, impacto de dominio/datos/API/eventos, seguridad,
multitenancy, auditoría, pruebas y rollback.

Después de implementar, informar archivos, decisiones, migraciones y contratos,
comandos ejecutados, resultados reales, pruebas, controles de aislamiento,
seguridad, documentación, limitaciones y siguiente tarea cronológica.

No afirmar que una prueba pasó si no fue ejecutada. No guardar secretos,
credenciales, modelos ni telemetría sensible en Git. No introducir dependencias
sin justificación y revisión. Toda decisión arquitectónica se registra en un
ADR.
