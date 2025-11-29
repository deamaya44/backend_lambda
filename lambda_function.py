import json
import os
import boto3
import psycopg2
from psycopg2.extras import RealDictCursor
from botocore.exceptions import ClientError

# Environment variables
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_SECRET_ARN = os.environ.get('DB_SECRET_ARN')  # ARN del secret en Secrets Manager
DB_PORT = os.environ.get('DB_PORT', '5432')

# Cache para la contraseña
_db_password_cache = None

def get_secret_value(secret_arn):
    """Obtiene el valor del secret desde AWS Secrets Manager usando IAM role"""
    global _db_password_cache
    
    if _db_password_cache is not None:
        return _db_password_cache
    
    try:
        # Usar boto3 sin credenciales explícitas - usa el IAM role de la Lambda
        client = boto3.client('secretsmanager')
        response = client.get_secret_value(SecretId=secret_arn)
        
        # El secret puede estar en 'SecretString' o 'SecretBinary'
        if 'SecretString' in response:
            secret = response['SecretString']
            # Si es JSON, parsearlo
            try:
                secret_dict = json.loads(secret)
                # Buscar la contraseña en diferentes formatos posibles
                password = secret_dict.get('password') or secret_dict.get('Password') or secret
            except json.JSONDecodeError:
                # Si no es JSON, es la contraseña directamente
                password = secret
        else:
            # Si es binario, decodificarlo
            password = response['SecretBinary'].decode('utf-8')
        
        _db_password_cache = password
        return password
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"Error obteniendo secret: {error_code} - {e}")
        raise Exception(f"No se pudo obtener la contraseña de la base de datos: {error_code}")

def get_db_connection():
    """Create and return a database connection"""
    try:
        # Obtener password desde Secrets Manager usando IAM role
        db_password = get_secret_value(DB_SECRET_ARN)
        
        # Remover el puerto del host si viene incluido
        db_host = DB_HOST.split(':')[0] if ':' in DB_HOST else DB_HOST
        
        conn = psycopg2.connect(
            host=db_host,
            database=DB_NAME,
            user=DB_USER,
            password=db_password,
            port=DB_PORT,
            connect_timeout=5,
            sslmode='require'
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        raise

def handler(event, context):
    """
    Lambda handler function
    Handles HTTP requests from API Gateway or Function URL
    """
    
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }
    
    try:
        # Handle OPTIONS request for CORS
        if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'OK'})
            }
        
        # Extract HTTP method and path
        http_method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
        path = event.get('requestContext', {}).get('http', {}).get('path', '/')
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Route handling
        if path == '/health' or path == '/':
            response_body = {
                'status': 'healthy',
                'message': 'API is running',
                'database': 'connected'
            }
            status_code = 200
            
        elif path == '/users' and http_method == 'GET':
            # Get all users
            cursor.execute('SELECT id, name, email, created_at FROM users ORDER BY id')
            users = cursor.fetchall()
            response_body = {
                'users': users,
                'count': len(users)
            }
            status_code = 200
            
        elif path.startswith('/users/') and http_method == 'GET':
            # Get user by ID
            user_id = path.split('/')[-1]
            cursor.execute('SELECT id, name, email, created_at FROM users WHERE id = %s', (user_id,))
            user = cursor.fetchone()
            
            if user:
                response_body = {'user': user}
                status_code = 200
            else:
                response_body = {'error': 'User not found'}
                status_code = 404
                
        elif path == '/users' and http_method == 'POST':
            # Create new user
            body = json.loads(event.get('body', '{}'))
            name = body.get('name')
            email = body.get('email')
            
            if not name or not email:
                response_body = {'error': 'Name and email are required'}
                status_code = 400
            else:
                cursor.execute(
                    'INSERT INTO users (name, email) VALUES (%s, %s) RETURNING id, name, email, created_at',
                    (name, email)
                )
                new_user = cursor.fetchone()
                conn.commit()
                
                response_body = {
                    'message': 'User created successfully',
                    'user': new_user
                }
                status_code = 201
                
        else:
            response_body = {'error': 'Route not found'}
            status_code = 404
        
        # Close database connection
        cursor.close()
        conn.close()
        
        return {
            'statusCode': status_code,
            'headers': headers,
            'body': json.dumps(response_body, default=str)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }
