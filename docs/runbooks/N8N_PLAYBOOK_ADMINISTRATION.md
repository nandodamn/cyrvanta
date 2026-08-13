# Administración del adaptador n8n opcional

**Estado:** n8n es opcional; `Cyrvanta Native` es el motor predeterminado.

Este runbook prepara una instancia n8n real sin otorgarle autoridad de negocio.
PostgreSQL conserva playbooks, autorizaciones, ejecuciones y resultados. n8n no
aprueba acciones y un ACK HTTP nunca equivale a éxito.

## Condiciones previas

- Use una instancia o proyecto con aislamiento administrativo verificable para
  el tenant; en caso contrario, una instancia dedicada.
- Mantenga `N8N_ENABLED=false`, bindings N8N inactivos, switches LIVE apagados
  y kill switch disponible durante la configuración.
- El editor sólo se publica en loopback o en una red administrativa protegida.
- No configure secretos en Git, argumentos, logs o JSON de workflow.
- No habilite el adaptador hasta completar una aceptación específica de la
  misma instancia, workflow, digest, callbacks y destinos reales.

## Configuración normal en Cyrvanta

En **Integraciones** cree una conexión `N8N` con:

- URL base interna de la instancia;
- API key administrativa write-only;
- nombre no sensible de la conexión.

Guarde, habilite y ejecute **Probar conexión real**. El probe consulta de forma
acotada la API de workflows con `X-N8N-API-KEY`; sólo conserva salud, latencia,
fecha y código de error redactado. La API key nunca vuelve a mostrarse.

Una conexión saludable no habilita dispatch, no publica workflows y no activa
bindings por sí sola.

## Secretos internos

Dispatch y callback usan claves separadas por propósito. Normalmente se derivan
de la clave maestra de instalación con versión explícita y leases de un solo
uso para el adaptador. Los overrides de despliegue son write-only y sólo deben
usarse durante una migración coordinada.

- La clave de dispatch firma Cyrvanta → n8n.
- La clave de callback firma n8n → Cyrvanta.
- Ninguna clave administrativa, de dispatch o callback se guarda en artefactos
  de playbook.
- La rotación conserva una ventana controlada para callbacks en vuelo y genera
  auditoría sin valores.

## Workflows como código

Antes de importar o actualizar:

1. valide manifest, schemas, digest y artefacto;
2. confirme que no haya credential IDs ni valores secretos;
3. permita sólo nodos y expresiones del contrato aprobado;
4. prohíba shell, SSH, Code/Function, filesystem, Git, base de datos,
   community nodes y subworkflows no registrados;
5. compruebe que todo camino con efecto exige primero un claim `proceed` de
   Cyrvanta;
6. ejecute reconciliación en modo diff redactado;
7. aplique sólo el diff revisado y nunca borre automáticamente recursos.

Las credenciales de correo, ticketing u otros proveedores se administran dentro
del límite autorizado de n8n con cuentas de mínimo privilegio. Cyrvanta sólo
muestra aliases y estado; nunca IDs o valores.

## Binding por playbook

1. Publique una versión lógica inmutable en Cyrvanta.
2. Registre el workflow instalado y su digest observado.
3. Cree un binding `N8N` para esa versión e instancia.
4. Ejecute probe y compruebe estado sincronizado, workflow activo y ausencia de
   drift.
5. Verifique que la conexión tenant-scoped aceptada y la instancia usada por el
   dispatcher sean la misma. Si esta comprobación no está disponible, el
   binding debe permanecer inactivo.
6. Active el binding sólo tras aceptación operativa específica.

Cambiar `NATIVE | N8N` no reescribe el playbook lógico ni ejecuciones históricas.

## Ejecución segura

Una ejecución N8N válida debe demostrar:

1. autorización activa consumida una sola vez;
2. ejecución y outbox creados atómicamente;
3. binding tenant-scoped y digest coincidente;
4. dispatch HMAC con timestamp y nonce;
5. claim durable anterior a cualquier efecto;
6. intento y outcome técnico append-only;
7. callback HMAC idempotente con schema estricto;
8. estado terminal persistido en Cyrvanta;
9. correlación, causalidad y auditoría reconstruibles.

Timeout, ACK ambiguo, callback inválido, replay, drift o caída de n8n nunca se
presentan como éxito.

## Desactivación y rollback

1. Active el kill switch si existe riesgo de egreso no deseado.
2. Desactive nuevos bindings N8N y `N8N_ENABLED`.
3. Conserve ejecuciones reclamadas para conciliación; no reactive
   autorizaciones consumidas.
4. Desactive workflows administrados sin borrarlos.
5. No elimine volumen, credenciales, historia, outcomes, callbacks o DLQ.
6. Reasigne futuras versiones a `Cyrvanta Native` cuando corresponda.

## Pruebas no ejecutadas por Codex

Codex no consultó la API n8n, no importó workflows, no probó credenciales, no
activó bindings y no ejecutó acciones. La aceptación del adaptador debe ser
manual y específica del entorno.