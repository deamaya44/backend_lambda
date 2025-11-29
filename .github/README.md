# GitHub Actions Configuration

Este repositorio contiene el workflow de CI/CD para el despliegue automático del backend Lambda.

## Workflow: Deploy Backend Lambda

El workflow construye el paquete Lambda y actualiza las funciones en ambas regiones.

**Importante:** Las funciones Lambda deben existir previamente (creadas por Terraform). Este workflow solo **actualiza el código**.

## Secrets Requeridos

Configura los siguientes secrets en tu repositorio:

### Settings > Secrets and variables > Actions > New repository secret

1. **`AWS_ACCESS_KEY_ID`**
   - Access Key ID de un usuario IAM con permisos para Lambda

2. **`AWS_SECRET_ACCESS_KEY`**
   - Secret Access Key correspondiente

3. **`LAMBDA_FUNCTION_NAME`**
   - Nombre de la función Lambda en región primaria
   - Ejemplo: `multiregion-dev-api`
   - Obtener con: `terraform output lambda_function_name`

4. **`LAMBDA_FUNCTION_NAME_SECONDARY`**
   - Nombre de la función Lambda en región secundaria
   - Ejemplo: `multiregion-dev-api-2`
   - Obtener con: `terraform output lambda_function_name_2`

## Permisos IAM Requeridos

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration"
      ],
      "Resource": [
        "arn:aws:lambda:us-east-1:*:function:multiregion-*-api",
        "arn:aws:lambda:us-west-2:*:function:multiregion-*-api-2"
      ]
    }
  ]
}
```

## Flujo de Despliegue

1. **Checkout del código**
2. **Setup Python 3.11**
3. **Build del paquete:**
   - Instala dependencias en directorio `package/`
   - Copia `lambda_function.py`
   - Crea `lambda_function.zip`
4. **Configuración de credenciales AWS**
5. **Update Lambda us-east-1** - Actualiza código de la función primaria
6. **Update Lambda us-west-2** - Actualiza código de la función secundaria
7. **Summary** - Muestra resumen del despliegue

## Prerequisitos

**IMPORTANTE:** Antes de usar este workflow, debes:

1. ✅ Desplegar la infraestructura con Terraform:
   ```bash
   cd ../multiregion
   terraform init
   terraform apply
   ```

2. ✅ Las funciones Lambda deben existir en AWS
3. ✅ Los recursos de RDS, VPC, Security Groups deben estar creados

Este workflow **NO crea** las funciones Lambda, solo **actualiza el código**.

## Uso

### Despliegue Automático
```bash
git add .
git commit -m "Update Lambda code"
git push origin main
```

### Despliegue Manual
1. Ve a **Actions** en GitHub
2. Selecciona **Deploy Backend Lambda**
3. Click en **Run workflow**

## Obtener Nombres de Funciones Lambda

Desde tu proyecto Terraform:

```bash
cd /path/to/multiregion/multiregion
terraform output lambda_function_arn
# Extrae el nombre de la función del ARN
```

O busca directamente:
```bash
aws lambda list-functions --region us-east-1 --query 'Functions[?contains(FunctionName, `multiregion`)].FunctionName'
```

## Verificación Post-Despliegue

```bash
# Verificar versión actualizada en us-east-1
aws lambda get-function --function-name multiregion-dev-api --region us-east-1 \
  --query 'Configuration.LastModified'

# Verificar versión actualizada en us-west-2
aws lambda get-function --function-name multiregion-dev-api-2 --region us-west-2 \
  --query 'Configuration.LastModified'

# Invocar para probar
aws lambda invoke --function-name multiregion-dev-api \
  --payload '{"requestContext":{"http":{"path":"/health","method":"GET"}}}' \
  --region us-east-1 \
  response.json
  
cat response.json
```

## Estrategia de Despliegue

### Primera vez (con Terraform):
```bash
# 1. Crear infraestructura completa
cd multiregion
terraform apply

# 2. Las Lambdas se crean con código inicial
# 3. Configurar GitHub Actions secrets
```

### Actualizaciones de código (con GitHub Actions):
```bash
# Solo modificar código de Lambda
cd backend_lambda
# Hacer cambios en lambda_function.py
git commit -m "Update API logic"
git push

# GitHub Actions automáticamente:
# - Construye el paquete
# - Actualiza ambas funciones Lambda
```

## Troubleshooting

### Error: "ResourceNotFoundException"
- Las funciones Lambda no existen
- Ejecuta `terraform apply` primero

### Error: "Access Denied"
- Verifica permisos IAM
- Asegúrate que el usuario tenga `lambda:UpdateFunctionCode`

### Error: "RequestEntityTooLargeException"
- El paquete zip es mayor a 50MB
- Considera usar Lambda Layers para dependencias
- O usar ECR con container image

### Función no actualiza
- Verifica que el nombre sea correcto
- Espera a que `function-updated` complete
- Revisa CloudWatch Logs
