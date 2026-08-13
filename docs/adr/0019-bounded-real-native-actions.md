# ADR 0019 — Acciones nativas reales acotadas

Estado: `ACEPTADO — 2026-08-13`

## Contexto

PHASE 21-A entregó el motor nativo con ejecución exclusivamente simulada. La demostración a
clientes requiere probar la implementación final en un tenant de laboratorio, sin presentar
simuladores como funcionalidad real. Habilitar conectores externos en bloque ampliaría
innecesariamente el riesgo y exigiría credenciales e infraestructura de cada proveedor.

## Decisión propuesta

Introducir LIVE de forma incremental por acción. La primera acción será una transición interna
de incidente, sin egress ni credenciales, sujeta a aprobación independiente, idempotencia,
optimistic locking, aislamiento tenant y kill switch. El mismo código será desplegable en
laboratorio y producción; sólo cambia la configuración y los datos del entorno.

## Consecuencias

- La demo ejercita el motor y un efecto real, no un adaptador simulado.
- LIVE continúa apagado por defecto y no se habilita globalmente por la mera existencia del
  conector.
- Los conectores externos reales se incorporarán individualmente con contratos posteriores.
- Los artefactos `simulate-*` permanecen sólo como material de desarrollo heredado y quedan
  fuera del recorrido principal de cliente.

## Contrato rector

`docs/specifications/PHASE_21B_REAL_NATIVE_ACTIONS.md`.
