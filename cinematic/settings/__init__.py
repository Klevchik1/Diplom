import os
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv('DJANGO_ENVIRONMENT', 'development')

if ENVIRONMENT == 'production':
    from .production import *
else:
    from .development import *