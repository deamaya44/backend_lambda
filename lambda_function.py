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
    
    # Headers (CORS is handled by Lambda Function URL configuration)
    headers = {
        'Content-Type': 'application/json'
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
        
        # Route handling
        if path == '/health' or path == '/':
            # Health check doesn't need DB connection
            try:
                conn = get_db_connection()
                conn.close()
                db_status = 'connected'
            except:
                db_status = 'error'
            
            response_body = {
                'status': 'healthy',
                'message': 'API is running',
                'database': db_status
            }
            status_code = 200
            
            return {
                'statusCode': status_code,
                'headers': headers,
                'body': json.dumps(response_body, default=str)
            }
        
        # For other routes, connect to database
        conn = get_db_connection()
        
        if path == '/init-db' and http_method == 'POST':
            # Initialize database - create users table (use normal cursor for this)
            cursor = conn.cursor()
            init_sql = """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql';
            
            DROP TRIGGER IF EXISTS update_users_updated_at ON users;
            CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            
            INSERT INTO users (name, email) VALUES 
                ('John Doe', 'john@example.com'),
                ('Jane Smith', 'jane@example.com'),
                ('Bob Wilson', 'bob@example.com')
            ON CONFLICT (email) DO NOTHING;
            """
            
            cursor.execute(init_sql)
            conn.commit()
            
            cursor.execute('SELECT COUNT(*) FROM users')
            user_count = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'message': 'Database initialized successfully',
                    'user_count': user_count
                })
            }
        
        # For other routes, use RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if path == '/users' and http_method == 'GET':
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
        
        elif path.startswith('/users/') and http_method == 'DELETE':
            # Delete user by ID
            user_id = path.split('/')[-1]
            
            # Check if user exists
            cursor.execute('SELECT id FROM users WHERE id = %s', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                response_body = {'error': 'User not found'}
                status_code = 404
            else:
                cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
                conn.commit()
                
                response_body = {
                    'message': 'User deleted successfully',
                    'id': int(user_id)
                }
                status_code = 200
                
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
