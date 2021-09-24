# -*- coding: utf-8 -*-
"""
Django settings for core project.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

from pathlib import Path
import os
import environ
import logging
import logging.config
from corsheaders.defaults import default_headers

# import pprint

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# populate os.environ with .env settings
env = environ.Env()
env.read_env(env.str("ENV_PATH", "core/.env"))

# since this app usually runs behind one or more reverse proxies that may/not
# have X-Forwarded-For header set correctly, allow for explicit root URI
# to be set here via env.
# NOTE this value should *NOT* contain a trailing slash
BASE_URL = os.environ.get("BASE_URL", None)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
# env.bool is tricky to get right so opt for strict string comparison
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# tie together multiple log lines with a common id
REQUEST_ID_CONFIG = {
    "REQUEST_ID_HEADER": "HTTP_X_REQUEST_ID",
    "GENERATE_REQUEST_ID_IF_NOT_FOUND": True,
    "RESPONSE_HEADER_REQUEST_ID": "HTTP_X_REQUEST_ID",
}

ALLOWED_HOSTS = [
    "localhost",
    ".dol.gov",
    ".unemployment.gov",
    ".ui.gov",
]

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("core")
if os.environ.get("COLOR_LOGGING", "false").lower() == "true":
    LOGGING_CONFIG = None  # This empties out Django's logging config
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "request_id_django_log.filters.RequestIDFilter"}
        },
        "formatters": {
            "colored": {
                "()": "colorlog.ColoredFormatter",  # colored output
                # --> %(log_color)s is very important, that's what colors the line
                "format": "%(log_color)s[%(levelname)s] %(reset)s %(green)s[%(request_id)s] %(reset)s%(blue)s%(name)s - %(asctime)s :: %(reset)s %(message)s",
                "log_colors": {
                    "DEBUG": "blue",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            },
            # TODO determine config for CloudWatch
            "aws": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "colorlog.StreamHandler",
                "formatter": "colored",
                "filters": ["request_id"],
            },
        },
        "loggers": {
            "": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        },
    }
    logging.config.dictConfig(LOGGING)  # Finally replace our config in python logging

# Application definition

INSTALLED_APPS = [
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "api",
    "login-dot-gov",
    "secure_redis",
    "home",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "request_id_django_log.middleware.RequestIdDjangoLog",
]

ROOT_URLCONF = "core.urls"

WSGI_APPLICATION = "core.wsgi.application"

# caching. sessions use the same cache, but have a custom serializer
REDIS_DB = 0
REDIS_URL = os.environ.get(
    "REDIS_URL", f"rediss://host.docker.internal:6379/{REDIS_DB}"
)
redis_base_options = {
    "DB": REDIS_DB,
    "CLIENT_CLASS": "django_redis.client.DefaultClient",
    "SOCKET_CONNECT_TIMEOUT": 5,  # in seconds
    "SOCKET_TIMEOUT": 5,  # seconds
    "CONNECTION_POOL_KWARGS": {"ssl_cert_reqs": None},
    "REDIS_CLIENT_KWARGS": {"ssl": True, "ssl_cert_reqs": None},
}
if os.environ.get("REDIS_HOST"):
    # in WCMS env the config is set with separate env vars.
    REDIS_URL = f"rediss://{os.environ.get('REDIS_HOST')}:{os.environ.get('REDIS_PORT', '6379')}/{REDIS_DB}"
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": redis_base_options
        | {
            # 'PARSER_CLASS': 'redis.connection.HiredisParser',
            # A URL-safe base64-encoded 32-byte key.
            "REDIS_SECRET_KEY": os.environ.get("REDIS_SECRET_KEY"),
            "SERIALIZER": "secure_redis.serializer.SecureSerializer",
        },
        "KEY_PREFIX": "claimantsapi:secure",
        "TIMEOUT": 60 * 30,  # expire in 30 minutes TODO security requirement
    },
    "insecure": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": redis_base_options
        | {
            # 'PARSER_CLASS': 'redis.connection.HiredisParser',
        },
        "KEY_PREFIX": "claimantsapi",
        "TIMEOUT": 60 * 60 * 24,  # 1 day
    },
}
# logger.debug("CACHES={}".format(pprint.pformat(CACHES)))
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_SAVE_EVERY_REQUEST = True  # keep-alive on each request
SESSION_EXPIRY = env.int(
    "SESSION_EXPIRY", 30 * 60
)  # 30 minute timeout on no requests TODO
SESSION_COOKIE_AGE = env.int("SESSION_EXPIRY", 30 * 60)
# allow XHR/CORS to work in local dev with http/https mix,
# SESSION_COOKIE_SAMESITE is set to None in the .env-example for dev.
# NOTE that this assumes you are running react app on http and django on https behind proxy
# Chrome requires SameSite=None to be paired with Secure
SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Strict")
SESSION_COOKIE_SECURE = (
    os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
)

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases
if os.environ.get("DATABASE_URL"):
    default_db = env.db_url("DATABASE_URL")
    # allow for password to be stored separately from connection string
    if not default_db["PASSWORD"]:
        default_db["PASSWORD"] = env("DATABASE_PASSWORD")
elif os.environ.get("DB_SCHEMA"):
    default_db = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env.str("DB_SCHEMA"),
        "USER": env.str("DB_ADMIN_USER"),
        "PASSWORD": env.str("DB_PWD"),
        "HOST": "mysql-service",  # WCMS creates DNS entry for this
        "PORT": "3306",
    }
else:
    default_db = {"ENGINE": "django.db.backends.sqlite3", "NAME": "mydatabase"}


if "mysql" in default_db["ENGINE"]:
    default_db["OPTIONS"] = {
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO'"
    }

# logger.debug("DATABASES={}".format(pprint.pformat(default_db)))

DATABASES = {"default": default_db}


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATICFILES_DIRS = (os.path.join(BASE_DIR, "initclaim", "build", "static"),)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "initclaim")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS Cross-Origin Configuration
# https://github.com/adamchainz/django-cors-headers
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGIN_REGEXES = env.list("CORS_ALLOWED_ORIGIN_REGEXES", default=[])
# important to allow cookie to pass through
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [
    "Cache-Control",
    "If-Modified-Since",
    "Keep-Alive",
    "X-Requested-With",
    "X-DOL",
]

# Identity Providers
LOGIN_DOT_GOV_REDIRECT_URI = os.environ.get("LOGIN_DOT_GOV_REDIRECT_URI")
LOGIN_DOT_GOV_SCOPES = [
    "openid",
    "email",
    "phone",
    "address",
    "profile",
    "social_security_number",
]
LOGIN_DOT_GOV_CLIENT_ID = os.environ.get("LOGIN_DOT_GOV_CLIENT_ID")

if os.environ.get("LOGIN_DOT_GOV_ENV") == "test":
    # generate a new key pair on the fly
    from jwcrypto import jwk
    from jwcrypto.common import json_decode

    # use only 1024 bits since this is temporary key and we favor speed.
    client_private_key_jwk = jwk.JWK.generate(kty="RSA", size=1024)
    LOGIN_DOT_GOV_PRIVATE_KEY = client_private_key_jwk.export_to_pem(True, None).decode(
        "utf-8"
    )
    client_public_key_jwk = jwk.JWK()
    client_public_key_jwk.import_key(
        **json_decode(client_private_key_jwk.export_public())
    )
    LOGIN_DOT_GOV_PUBLIC_KEY = client_public_key_jwk.export_to_pem().decode("utf-8")
else:  # pragma: no cover
    logindotgov_private_key = ""
    private_key_file = (
        BASE_DIR
        / "certs"
        / os.environ.get("LOGIN_DOT_GOV_PRIVATE_KEY_FILE", "logindotgov-private.pem")
    )
    from os.path import exists as file_exists

    if file_exists(private_key_file):
        with open(private_key_file, "rb") as pf:
            logindotgov_private_key = pf.read()
        LOGIN_DOT_GOV_PRIVATE_KEY = logindotgov_private_key
    else:
        logger.warn("LOGIN_DOT_GOV_PRIVATE_KEY set to False as .pem could not be found")
        LOGIN_DOT_GOV_PRIVATE_KEY = False
