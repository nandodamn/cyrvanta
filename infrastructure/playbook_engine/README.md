# Cyrvanta Playbook Engine

Artefactos reproducibles del formato portable v1 aprobado en Fase 21-A.

- `schemas/playbook-v1.schema.json`: JSON Schema publicado.
- `fixtures/simulated-notification.json`: ejemplo válido sin secretos.
- `fixtures/invalid-arbitrary-code.json`: fixture negativo de código prohibido.
- `scripts/export_schema.py`: exporta el schema desde el modelo Pydantic
  autoritativo y permite verificar que el archivo publicado no deriva.

Desde `backend`, validar con:

```powershell
python ../infrastructure/playbook_engine/scripts/export_schema.py
pytest tests/unit/test_portable_playbook.py
```

El artefacto sólo contiene aliases lógicos de credenciales. Nunca deben
agregarse tokens, passwords, API keys, cookies o certificados privados a estos
archivos.

