import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Base directory of the application
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Configuration class for different environments
class Config:
    """Base configuration class"""
    # API settings
    API_TITLE = 'Route Optimizer API'
    API_VERSION = '1.0.0'
    API_DESCRIPTION = 'An API service for route optimization using AI/ML techniques'
    
    # Directories
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    MODELS_DIR = os.path.join(BASE_DIR, 'models')
    CACHE_DIR = os.path.join(DATA_DIR, 'cache')
    
    # Create necessary directories
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    # API keys and services
    OPENSTREETMAP_USER_AGENT = 'RouteOptimizer/1.0'
    
    # Rate limits (requests per second)
    GEOCODING_RATE_LIMIT = 1  # Max 1 request per second for Nominatim
    
    # Logging configuration
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = os.path.join(BASE_DIR, 'logs', 'api.log')
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # Database configuration (can be overridden by environment variables)
    DATABASE_URI = os.getenv('DEV_DATABASE_URI', f'sqlite:///{os.path.join(Config.DATA_DIR, "dev.db")}')

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = False
    TESTING = True
    
    # Use in-memory database for testing
    DATABASE_URI = os.getenv('TEST_DATABASE_URI', 'sqlite:///:memory:')
    
    # Override data directories for testing
    DATA_DIR = os.path.join(BASE_DIR, 'tests', 'data')
    CACHE_DIR = os.path.join(DATA_DIR, 'cache')
    
    # Create test directories
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Database configuration for production
    DATABASE_URI = os.getenv('PROD_DATABASE_URI', f'sqlite:///{os.path.join(Config.DATA_DIR, "prod.db")}')
    
    # Logging
    LOG_LEVEL = logging.WARNING

# Dictionary mapping environment names to configuration classes
config_dict = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Function to get configuration based on environment
def get_config(env_name=None):
    """Get configuration for the specified environment"""
    if env_name is None:
        env_name = os.getenv('FLASK_ENV', 'default')
    return config_dict.get(env_name, config_dict['default'])

# Set up logging
def setup_logging(config=None):
    """Set up logging with configuration"""
    if config is None:
        config = get_config()
    
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format=config.LOG_FORMAT,
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler()
        ]
    )