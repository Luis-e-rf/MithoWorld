# Guía de Inicio y Desarrollo - MithoWorld

Esta guía contiene los comandos esenciales para levantar el entorno de desarrollo en el servidor.

## 1. Conexión al Servidor
Desde VS Code, usar **Remote Explorer** y conectar al host `server-ubuntu-vscode`.

## 2. Preparar la Terminal
Una vez dentro, abrir la terminal (Ctrl + `) y navegar a la carpeta del proyecto si no estás allí:
```bash
cd ~/Proyectos/MithoWorld
```

## 3. Base de Datos (Docker)
Verificar si el contenedor de PostgreSQL está corriendo:
```bash
docker ps
```
Si no está corriendo (o si reiniciaste el servidor), levántalo:
```bash
docker-compose up -d
```

## 4 Levantar el Servidor Django
Para exponer la API en tu red local (y que sea accesible vía túnel o IP):
```bash
uv run python manage.py runserver 0.0.0.0:8080
```

## 6. URLs importantes
* API Root: http://localhost:8080/api/criaturas/
* Admin Panel: http://localhost:8080/admin/

## Comandos Útiles
Crear migraciones (si cambias models.py): 
```bash
uv run python manage.py makemigrations
```
Aplicar migraciones: 
```bash
uv run python manage.py migrate
```
Crear superusuario: 
```bash
uv run python manage.py createsuperuser
```