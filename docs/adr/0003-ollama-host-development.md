# ADR 0003 — Ollama en el host durante desarrollo

- Estado: Aceptado por Foundation
- Fecha: 2026-07-27
- Alcance: desarrollo en laptop Windows

## Contexto

El entorno objetivo usa Windows 11, Docker Desktop/WSL2 y Ollama local.

## Decisión

Ollama se ejecutará en el host y los contenedores usarán una URL configurable,
con valor de desarrollo habitual
`http://host.docker.internal:11434`. El proveedor y modelo se configurarán, no
se hardcodearán. Gemma 4 es la familia inicial. Toda llamada atravesará el
puerto `AIProvider`, implementado por infraestructura y consumido desde casos
de uso ejecutados normalmente por workers.

## Consecuencias

- Producción puede cambiar endpoint o proveedor sin cambiar dominio.
- Firewall, exposición, timeouts, concurrencia y disponibilidad son
  configuración operativa.
- La salida requiere schema y validación determinística.
- La ausencia de Ollama degrada la IA, no el acceso a incidentes existentes.

## Alternativas descartadas

Ollama dentro del perfil Compose de desarrollo y llamadas directas desde React.
