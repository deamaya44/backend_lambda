#!/bin/bash

# Script para crear el paquete de despliegue de Lambda usando Docker
# Esto garantiza compatibilidad con el runtime de Lambda

set -e

echo "🚀 Creando paquete de despliegue Lambda con Docker..."

# Limpiar directorio anterior si existe
rm -rf package lambda_function.zip

# Crear directorio para el paquete
mkdir -p package

# Usar imagen de Docker compatible con Lambda Python 3.11
echo "🐳 Instalando dependencias en contenedor Docker (Python 3.11)..."
docker run --rm \
    -v "$PWD":/var/task \
    -w /var/task \
    public.ecr.aws/lambda/python:3.11 \
    pip install -r requirements.txt -t package/ --quiet

# Copiar código de la función
echo "📋 Copiando código de función..."
cp lambda_function.py package/

# Crear archivo ZIP
echo "🗜️  Creando archivo ZIP..."
cd package
zip -r ../lambda_function.zip . -q
cd ..

# Limpiar directorio temporal
rm -rf package

echo "✅ Paquete creado: lambda_function.zip"
echo "📊 Tamaño: $(du -h lambda_function.zip | cut -f1)"
