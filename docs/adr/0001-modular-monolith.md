# ADR 0001 — Monolito modular

- Estado: Aceptado por Foundation
- Fecha: 2026-07-27
- Alcance: arquitectura inicial y MVP

## Contexto

El demo y MVP requieren límites fuertes sin asumir el coste operativo y
transaccional de microservicios prematuros.

## Decisión

El núcleo será un monolito modular con puntos de entrada separados para API,
worker y scheduler. Los bounded contexts se comunican mediante servicios de
aplicación, eventos de dominio o puertos explícitos. Ningún módulo importa la
persistencia de otro. Las tareas largas se entregan mediante RabbitMQ.

## Consecuencias

- Despliegue y depuración iniciales más simples.
- Transacciones locales cuando correspondan.
- Límites deben ser comprobables mediante reglas y pruebas.
- Un módulo solo podrá extraerse tras una necesidad medida y otro ADR.

## Alternativas descartadas

Microservicios completos, Kafka y service mesh durante el MVP.
