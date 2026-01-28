# Manual de instalación  
**Proyecto:** Turnero  
**Stack:** Django + Django REST Framework + Google Calendar API  

Repositorio:  
https://github.com/guacho175/turnero.git

-----------------------------------------------------------------------------------------------------

## 1) Requisitos previos

Antes de comenzar, verifica que tu sistema tenga instalado:

- **Python**
- **pip**
- **Git**
- Soporte para entornos virtuales (`venv`)
-----------------------------------------------------------------------------------------------------

### Verificación
```powershell
python --version
pip --version
git --version
```


-----------------------------------------------------------------------------------------------------

2) Clonar el repositorio
```
git clone https://github.com/guacho175/turnero.git
cd turnero
```
-----------------------------------------------------------------------------------------------------

3) Crear y activar entorno virtual
Crear entorno
```
python -m venv env
```
Activar entorno (PowerShell)

```
.\env\Scripts\Activate.ps1
```

-----------------------------------------------------------------------------------------------------

4) Instalar dependencias
Con el entorno virtual activo:
```
pip install -r requirements.txt
```
-----------------------------------------------------------------------------------------------------

5) Credenciales Google Calendar (obligatorio)
El proyecto requiere archivos locales para autenticación OAuth.

Estructura esperada
```
credentials/
 ├─ credentials.json   # OBLIGATORIO (OAuth Google)
 └─ token.json         # Se genera automáticamente (NO versionar)
 ```
Si el repositorio no incluye credenciales
Crear la carpeta:

mkdir credentials
Luego una de las siguientes opciones:

Solicitar credentials.json al responsable del proyecto, o

Crear credenciales OAuth en Google Cloud Console y descargar el archivo como:

credentials/credentials.json
Nota técnica:
Crear un credentials.json vacío NO autentica, solo evita errores de archivo inexistente.

-----------------------------------------------------------------------------------------------------

6) Ejecutar el servidor
Desde la carpeta donde se encuentra manage.py:
```
python manage.py runserver
```
Servidor disponible en:

http://127.0.0.1:8000/

-----------------------------------------------------------------------------------------------------

7) Prueba rápida del endpoint (POST)
```
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
```

-----------------------------------------------------------------------------------------------------
## Ejecución exitosa

![Prueba exitosa - creación de evento](docs/img/success.png)

La siguiente captura muestra la ejecución correcta del endpoint
`POST /calendar/events` desde PowerShell, retornando un evento **confirmado**
y el `htmlLink` generado por Google Calendar.


El evento fue creado correctamente en el calendario asociado a las credenciales OAuth.