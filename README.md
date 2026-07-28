# Cyrvanta

Cyrvanta es una plataforma empresarial multitenant de operaciones de
ciberseguridad asistida por IA. Correlaciona alertas, organiza incidentes,
enriquece evidencia con MITRE ATT&CK y permite respuestas controladas sin
ceder el control de datos, infraestructura o decisiones de autorización.

> Estado: **bootstrap técnico en implementación**. Incluye infraestructura base,
> identidad local mínima y UI inicial; los módulos SOC continúan pendientes.

## Principios

- Multitenancy y aislamiento desde la primera migración.
- Español e inglés como idiomas de primera clase.
- Autenticación local y LDAP/Active Directory.
- Seguridad, auditabilidad y deny-by-default.
- Monolito modular con puertos y adaptadores reemplazables.
- PostgreSQL como sistema de registro y OpenSearch para telemetría.
- IA consultiva y validada; autorización y ejecución determinísticas.
- Despliegue on-premise y datos bajo control del operador.

## Documentación

La lectura comienza en [`docs/foundation/README.md`](docs/foundation/README.md).
Las reglas para agentes están en [`AGENTS.md`](AGENTS.md). El roadmap y backlog
documental están en [`docs/ROADMAP.md`](docs/ROADMAP.md) y
[`docs/IMPLEMENTATION_BACKLOG.md`](docs/IMPLEMENTATION_BACKLOG.md).

Los documentos de `docs/domain/` fueron aprobados como base conceptual. Las
decisiones reversibles del bootstrap están registradas en ADR.

## Estado del entorno

Este árbol local comenzó sin metadatos Git. La asociación con
`https://github.com/nandodamn/cyrvanta` debe verificarse antes de publicar.

## Inicio local

1. Copiar `.env.example` a `.env` y reemplazar todas las credenciales.
2. Ejecutar `docker compose up -d --build` (`COMPOSE_PROFILES=core` está
   definido en `.env`).
3. Abrir `http://localhost:8080`.
4. Crear el administrador inicial:

```bash
docker compose --profile core run --rm backend python -m cyrvanta.bootstrap_admin \
  --tenant-name "Demo" --email "admin@example.test" --password "use-a-strong-password"
```

La API expone `/api/v1/health`, `/api/v1/ready`, `/api/v1/version` y OpenAPI
en `/api/docs` fuera de producción. PostgreSQL, Redis y RabbitMQ no publican
puertos al host.
