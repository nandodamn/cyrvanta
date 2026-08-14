# Certificado TLS del Wazuh Manager

El manager genera un certificado autofirmado propio en el primer arranque
(`CN=wazuh.com`, `SAN=DNS:localhost`) que **no** incluye el hostname real del
servicio (`wazuh-manager`), así que la verificación estricta de TLS del
código de producción (`verify=True` en
`playbooks/infrastructure/action_registry.py`) lo rechaza correctamente.

`certs/server.crt`/`server.key` reemplazan ese certificado por uno propio,
válido 10 años, con el SAN correcto. `server.key` no se commitea (ver
`.gitignore`) -- regenerarlo:

```bash
mkdir -p infrastructure/wazuh/manager/certs
cd infrastructure/wazuh/manager/certs
openssl req -x509 -newkey rsa:2048 -keyout server.key -out server.crt -days 3650 -nodes \
  -subj "/O=Cyrvanta Lab/CN=wazuh-manager" \
  -addext "subjectAltName=DNS:wazuh-manager,DNS:localhost"
```

`server.crt` (público) además se instala en el bundle de `certifi` de la
imagen `backend` (ver `backend/Dockerfile`) para que `httpx` confíe en él sin
debilitar `verify=True`. Si se regenera el certificado, hay que reconstruir
la imagen `backend` para que tome la copia nueva.
