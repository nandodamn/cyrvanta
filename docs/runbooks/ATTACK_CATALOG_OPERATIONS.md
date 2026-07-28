# Operación del catálogo MITRE ATT&CK

**Estado:** operativo para Etapa 5

El catálogo se importa offline. Ni Alembic ni el arranque de Cyrvanta descargan
datos de Internet.

## Obtener y verificar una release

Descargar el bundle desde una release oficial de
`mitre-attack/attack-stix-data` a una ruta temporal fuera del repositorio. Para
el baseline aprobado:

```powershell
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/v19.1/enterprise-attack/enterprise-attack.json" `
  -OutFile "C:\tmp\enterprise-attack-v19.1.json"
```

El importador rechaza archivos mayores a 250 MiB, bundles inválidos, exceso de
objetos/relaciones y tipos fuera de la allowlist.

## Importar y activar

Con el perfil core saludable:

```powershell
docker cp C:\tmp\enterprise-attack-v19.1.json `
  cyrvanta-backend-1:/tmp/enterprise-attack-v19.1.json

docker exec cyrvanta-backend-1 python -m cyrvanta.import_attack `
  /tmp/enterprise-attack-v19.1.json `
  --version 19.1 `
  --source-url "https://github.com/mitre-attack/attack-stix-data/releases/tag/v19.1" `
  --activate
```

La importación es idempotente si versión y SHA-256 coinciden. La misma versión
con contenido diferente falla cerrado. `--activate` retira la release activa
anterior sin borrar catálogo ni resultados históricos.

## Validación

1. `GET /api/v1/attack/techniques?q=T1078` debe devolver release `19.1`.
2. `POST /api/v1/incidents/{id}/risk-assessments` debe producir mappings,
   exactamente cinco factores y explicaciones deterministas ES/EN.
3. Repetir el POST con el mismo snapshot debe conservar el mismo assessment.
4. La prueba negativa con `app.current_tenant_id` de otro tenant debe devolver
   cero filas y rechazar escrituras por RLS.

## Rollback

Activar explícitamente una release previamente importada. No editar ni eliminar
mappings, evaluaciones o explicaciones históricas. El downgrade de la migración
se bloquea si existe cualquier dato ATT&CK o de riesgo.
