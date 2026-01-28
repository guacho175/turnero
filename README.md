# Manual de instalación (Django + DRF + Google Calendar)

## 1) Requisitos previos
Instala / verifica en tu PC:

- **Python 3.x**
- **pip** (viene con Python normalmente)
- **Git** (para clonar)
- Permiso para crear entornos virtuales (**venv**)

Verificación rápida:
```powershell
python --version
pip --version
git --version
2) Clonar el repositorio
git clone <URL_DEL_REPO>
cd <CARPETA_DEL_REPO>
3) Crear y activar entorno virtual
Crear:

python -m venv env
Activar (PowerShell):

.\env\Scripts\Activate.ps1
Si PowerShell bloquea scripts:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
4) Instalar dependencias
pip install -r requirements.txt
5) Credenciales Google Calendar (obligatorio)
Este proyecto requiere archivos locales en credentials/.

Estructura esperada:

credentials/credentials.json (OBLIGATORIO: se obtiene desde Google Cloud Console)

credentials/token.json (SE GENERA SOLO al autorizar; NO se sube al repo)

Si el repo viene sin credenciales
Crea la carpeta:

mkdir credentials
Luego:

Solicita credentials.json al responsable del proyecto, o

Crea tus propias credenciales OAuth en Google Cloud Console y descarga el JSON como credentials/credentials.json.

Nota: crear un credentials.json vacío NO sirve para autenticar; solo evita errores de “archivo no encontrado”.

6) Ejecutar el servidor
Desde la carpeta donde está manage.py:

python manage.py runserver
Servidor:

http://127.0.0.1:8000/

7) Prueba rápida (endpoint)
$body = @{
  summary = "Cita de prueba"
  start   = "2026-01-27T15:00:00-03:00"
  end     = "2026-01-27T15:30:00-03:00"
  description = "Creacion desde mi API"
  attendees = @()
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/calendar/events" `
  -ContentType "application/json" `
  -Body $body