# ADR 0018 — Motor nativo predeterminado y ciclo de secretos n8n

**Estado:** Aceptado  
**Fecha:** 2026-08-01

## Contexto

ADR 0015 introdujo n8n como adaptador de ejecución y ADR 0017 aprobó un motor
nativo restringido con coexistencia `NATIVE | N8N`. La configuración local aún
expone tres valores n8n al operador y el frontend los presenta con igual
jerarquía. Esto confunde una credencial administrativa aportada por el usuario
con dos secretos técnicos internos.

El producto debe funcionar sin n8n, conservar bindings por playbook y mantener
la seguridad de claim, callback, idempotencia, auditoría y rollback.

## Decisión

1. `Cyrvanta Native` es el motor predeterminado para nuevos bindings.
2. n8n es opcional globalmente y por playbook; su ausencia no degrada el motor
   nativo ni obliga a desplegar otro contenedor.
3. La configuración normal de n8n muestra sólo habilitación, URL y
   `N8N_API_KEY` write-only.
4. Las claves internas de dispatch y callback se generan con CSPRNG, se guardan
   mediante `DeploymentSecretStorePort`, se rotan explícitamente y sólo exponen
   metadata de presencia, versión y última rotación.
5. Ningún secreto guardado puede volver a leerse por API o UI. Sólo puede
   reemplazarse, probarse o rotarse.
6. El adaptador local on-premise cifra secretos en reposo mediante Fernet y una
   clave maestra de instalación suministrada fuera de Git. Producción puede
   sustituirlo por un gestor externo sin cambiar aplicación o dominio.
7. Cada versión portable mantiene identidad independiente del motor. Cambiar el
   binding no cambia ni reescribe el playbook lógico.
8. `LIVE` permanece deshabilitado hasta una aprobación operativa separada.
9. Toda preparación, reemplazo, prueba y rotación se audita sin valores.
10. El dashboard no presenta datos estáticos como actividad real; cuando una
    fuente sea simulada se etiqueta y, sin evidencia, muestra estado vacío.

## Consecuencias

- La instalación estándar puede operar sólo con PostgreSQL, RabbitMQ, Redis,
  backend, worker, scheduler, frontend y proxy.
- El perfil Docker `automation` continúa siendo la forma explícita de desplegar
  n8n.
- Permanece un secreto raíz inevitable de instalación, separado de las llaves
  administradas y nunca accesible desde la UI.
- La rotación coordinada debe soportar una ventana acotada de clave anterior
  para no perder callbacks en vuelo.
- La desactivación global de n8n detiene nuevos dispatch hacia ese adaptador,
  pero conserva bindings e historia.

## Compatibilidad y rollback

Los bindings `N8N` y su evidencia histórica no se modifican. Rollback operativo:
desactivar nuevos bindings nativos o reasignar futuras ejecuciones a un binding
n8n validado, sin reescribir versiones ni ejecuciones. Desactivar n8n nunca
elimina sus datos, claves, workflows o volumen.

## Aprobación

Aceptado por decisión humana explícita el 2026-08-01. La misma decisión exige
motor nativo predeterminado, n8n opcional globalmente y por playbook, secretos
técnicos automatizados/write-only, UI responsive y métricas reales o vacías.

