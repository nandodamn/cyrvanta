# ADR 0020 — Runtime real sin éxitos simulados

Estado: `ACEPTADO — 2026-08-13`

## Contexto

El producto conserva modos simulados y generadores sintéticos útiles durante el desarrollo.
Presentarlos en una demostración comercial puede confundir datos de prueba con capacidad final
y permitir que un conector informe éxito sin producir un efecto verificable.

## Decisión propuesta

El runtime distribuido utilizará exclusivamente capacidades reales o deshabilitadas. Se
retirarán rutas sintéticas de API/UI, se eliminará `simulated` como modo saludable y sólo se
publicarán playbooks con todas sus acciones reales configuradas. Los dobles permanecerán
exclusivamente en tests.

## Consecuencias

- Una instalación sin conexiones mostrará capacidades bloqueadas, no datos inventados.
- La demo requiere Wazuh/OpenSearch/Ollama/LDAP/SMTP/HTTP reales según el caso mostrado.
- Los playbooks no soportados permanecen visibles, explican sus dependencias y están deshabilitados.
- La activación LIVE sigue siendo gradual, auditable y deny-by-default.
- Los registros sintéticos históricos no se reclasifican y se excluyen de vistas operativas.

## Contratos rectores

- `docs/specifications/PHASE_24_REAL_RUNTIME_NO_SIMULATION.md`
- `docs/specifications/PHASE_21B_REAL_NATIVE_ACTIONS.md`
