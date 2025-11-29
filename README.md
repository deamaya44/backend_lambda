# Backend Lambda

API backend simple que se conecta a RDS PostgreSQL y expone endpoints REST.

## Estructura

```
backend_lambda/
├── lambda_function.py   # Código principal de la Lambda
├── requirements.txt     # Dependencias Python
├── Dockerfile          # Para despliegue como container image
├── deploy.sh           # Script de despliegue
└── README.md           # Este archivo
```

## Endpoints

- `GET /` o `/health` - Health check
- `GET /users` - Listar todos los usuarios
- `GET /users/{id}` - Obtener usuario por ID
- `POST /users` - Crear nuevo usuario (body: `{"name": "...", "email": "..."}`)

## Variables de Entorno Requeridas

- `DB_HOST` - Hostname de la base de datos RDS
- `DB_NAME` - Nombre de la base de datos
- `DB_USER` - Usuario de la base de datos
- `DB_SECRET_ARN` - ARN del secret en AWS Secrets Manager con la contraseña
- `DB_PORT` - Puerto (default: 5432)

**Nota importante:** La Lambda usa su IAM role para acceder a Secrets Manager. No se pasan credenciales directamente.

## Schema de Base de Datos

```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Datos de ejemplo
INSERT INTO users (name, email) VALUES 
    ('John Doe', 'john@example.com'),
    ('Jane Smith', 'jane@example.com');
```

## Despliegue

### Primera vez: Con Terraform

**IMPORTANTE:** El primer despliegue DEBE ser con Terraform para crear la infraestructura completa.

```bash
# 1. Crear paquete inicial
./deploy.sh

# 2. Desplegar infraestructura (desde directorio multiregion)
cd ../multiregion
terraform init
terraform apply

# Esto crea:
# - Funciones Lambda en ambas regiones
# - VPC, Security Groups, RDS, etc.
# - IAM roles con permisos necesarios
```

### Actualizaciones: Con GitHub Actions

Una vez la infraestructura existe, las actualizaciones de código se hacen automáticamente:

1. **Configurar GitHub Actions:**
   - Crear repositorio separado para el backend
   - Configurar secrets (ver `.github/README.md`)

2. **Deploy automático:**
```bash
# Hacer cambios en lambda_function.py
git add .
git commit -m "Update API endpoint"
git push origin main

# GitHub Actions automáticamente:
# - Instala dependencias
# - Crea lambda_function.zip
# - Actualiza ambas funciones Lambda
```

**Flujo:**
```
Terraform (primera vez) → Crea Lambda con código inicial
         ↓
GitHub Actions (updates) → Solo actualiza código de Lambda existente
```

## Configuración de Terraform

Este backend se despliega usando el módulo Lambda en el archivo `main.tf` de multiregion.

Las variables de entorno se configuran automáticamente desde Terraform:
- `DB_HOST` se obtiene del output de RDS
- `DB_SECRET_ARN` apunta al secret creado en Secrets Manager
- El IAM role de la Lambda tiene permisos para leer el secret

**Seguridad:** La contraseña nunca se expone como variable de entorno. La Lambda la obtiene dinámicamente desde Secrets Manager usando su IAM role.
