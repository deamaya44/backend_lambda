#!/bin/bash

# Script para crear el paquete de despliegue de Lambda

set -e

echo "🚀 Creando paquete de despliegue Lambda..."

# Limpiar directorio anterior si existe
rm -rf package lambda_function.zip

# Crear directorio para el paquete
mkdir -p package

# Instalar dependencias
echo "📦 Instalando dependencias..."
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
