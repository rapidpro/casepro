from __future__ import absolute_import, unicode_literals

import djcelery
import os
import sys

from datetime import timedelta
from django.utils.translation import ugettext_lazy as _

# -----------------------------------------------------------------------------------
# Sets TESTING to True if this configuration is read during a unit test
# -----------------------------------------------------------------------------------
TESTING = sys.argv[1:2] == ['test']

# Django settings for tns_glass project.
THUMBNAIL_DEBUG = False

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Nyaruka', 'code@nyaruka.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'casepro.sqlite',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

EMAIL_BACKEND = 'djcelery_email.backends.CeleryEmailBackend'
SEND_EMAILS = TESTING  # safe to send emails during tests as these use a fake backend

# dash configuration
SITE_API_HOST = 'http://localhost:8001/'
SITE_API_USER_AGENT = 'casepro/0.1'
SITE_HOST_PATTERN = 'http://%s.localhost:8000'
SITE_CHOOSER_URL_NAME = 'orgs_ext.org_chooser'
SITE_CHOOSER_TEMPLATE = 'org_chooser.haml'
SITE_USER_HOME = '/'
SITE_ALLOW_NO_ORG = ('orgs_ext.org_create', 'orgs_ext.org_update', 'orgs_ext.org_list',
                     'orgs_ext.task_list',
                     'profiles.user_create', 'profiles.user_update', 'profiles.user_read', 'profiles.user_list',
                     'internal.status', 'internal.ping')

# casepro configuration
SITE_ORGS_STORAGE_ROOT = 'orgs'
SITE_EXTERNAL_CONTACT_URL = 'http://localhost:8001/contact/read/%s/'
SITE_BACKEND = 'casepro.backend.NoopBackend'
SITE_ANON_CONTACTS = False


# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone
TIME_ZONE = 'GMT'
USER_TIME_ZONE = 'GMT'
USE_TZ = True

SITE_DATE_FORMAT = r'%b %d, %Y'

MODELTRANSLATION_TRANSLATION_REGISTRY = "translation"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en'

# Available languages for translation
LANGUAGES = (('en', _("English")), ('fr', _("French")))
RTL_LANGUAGES = {}
DEFAULT_LANGUAGE = "en"

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/sitestatic/'
COMPRESS_URL = '/sitestatic/'

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/sitestatic/admin/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

COMPRESS_PRECOMPILERS = (
    ('text/coffeescript', 'coffee --compile --stdio'),
    ('text/less', 'casepro.compress.LessFilter'),
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = '4-rr2sa6c#5*vr^2$m*2*j+5tc9duo2q+5e!xra%n($d5a$yp)'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'hamlpy.template.loaders.HamlPyFilesystemLoader',
    'hamlpy.template.loaders.HamlPyAppDirectoriesLoader',
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader'
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'dash.orgs.middleware.SetOrgMiddleware',
    'casepro.utils.middleware.JSONMiddleware',
    'casepro.profiles.middleware.ForcePasswordChangeMiddleware',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.contrib.messages.context_processors.messages',
    'django.core.context_processors.request',
    'dash.orgs.context_processors.user_group_perms_processor',
    'dash.orgs.context_processors.set_org_processor',
    'dash.context_processors.lang_direction',
    'casepro.cases.context_processors.sentry_dsn',
    'casepro.cases.context_processors.server_time',
    'casepro.profiles.context_processors.user',
)

ROOT_URLCONF = 'casepro.urls'

CACHES = {
    'default': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': '127.0.0.1:6379:15',
        'OPTIONS': {
            'CLIENT_CLASS': 'redis_cache.client.DefaultClient',
        }
    }
}

ORG_CONFIG_FIELDS = [dict(name='contact_fields',
                          field=dict(help_text=_("Contact fields to display"), required=False)),
                     dict(name='banner_text',
                          field=dict(help_text=_("Banner text displayed to all users"), required=False))]

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.postgres',

    'djcelery',
    'djcelery_email',

    # mo-betta permission management
    'guardian',

    # versioning of our data
    'reversion',

    # the django admin
    # 'django.contrib.admin',

    # compress our CSS and js
    'compressor',

    # thumbnail
    'sorl.thumbnail',

    # smartmin
    'smartmin',

    # import tasks
    'smartmin.csv_imports',

    # users
    'smartmin.users',

    # dash apps
    'dash.orgs',
    'dash.utils',

    # custom
    'casepro.orgs_ext',
    'casepro.profiles',
    'casepro.contacts',
    'casepro.msgs',
    'casepro.rules',
    'casepro.cases',
    'casepro.statistics',
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'httprouterthread': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
    }
}

# -----------------------------------------------------------------------------------
# Directory Configuration
# -----------------------------------------------------------------------------------
PROJECT_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))
RESOURCES_DIR = os.path.join(PROJECT_DIR, '../resources')

LOCALE_PATHS = (os.path.join(PROJECT_DIR, '../locale'),)
RESOURCES_DIR = os.path.join(PROJECT_DIR, '../resources')
FIXTURE_DIRS = (os.path.join(PROJECT_DIR, '../fixtures'),)
TESTFILES_DIR = os.path.join(PROJECT_DIR, '../testfiles')
TEMPLATE_DIRS = (os.path.join(PROJECT_DIR, '../templates'),)
STATICFILES_DIRS = (os.path.join(PROJECT_DIR, '../static'), os.path.join(PROJECT_DIR, '../media'), )
STATIC_ROOT = os.path.join(PROJECT_DIR, '../sitestatic')
MEDIA_ROOT = os.path.join(PROJECT_DIR, '../media')
MEDIA_URL = "/media/"

# -----------------------------------------------------------------------------------
# Permission Management
# -----------------------------------------------------------------------------------

# this lets us easily create new permissions across our objects
PERMISSIONS = {
    '*': ('create',  # can create an object
          'read',    # can read an object, viewing it's details
          'update',  # can update an object
          'delete',  # can delete an object,
          'list'),   # can view a list of the objects

    'orgs.org': ('create', 'update', 'list', 'home', 'edit', 'inbox', 'charts'),

    'msgs.label': ('create', 'update', 'read', 'delete', 'list'),

    'msgs.message': ('action', 'bulk_reply', 'forward', 'label', 'history', 'search', 'unlabelled'),

    'msgs.messageexport': ('create', 'read'),

    'msgs.outgoing': ('search', 'search_replies'),

    'msgs.replyexport': ('create', 'read'),

    'cases.case': ('create', 'read', 'update', 'list'),

    'case.caseexport': ('create', 'read'),

    'cases.partner': ('create', 'read', 'delete', 'list'),

    'contacts.contact': ('read', 'list'),

    'contacts.group': ('select', 'list'),

    # can't create profiles.user.* permissions because we don't own User
    'profiles.profile': ('user_create', 'user_create_in', 'user_update', 'user_read', 'user_list'),
}

# assigns the permissions that each group should have
GROUP_PERMISSIONS = {
    "Administrators": (  # Org users: Administrators
        'orgs.org_inbox',
        'orgs.org_home',
        'orgs.org_charts',
        'orgs.org_edit',

        'msgs.label.*',
        'msgs.message.*',
        'msgs.messageexport.*',
        'msgs.outgoing.*',
        'msgs.replyexport.*',

        'cases.case.*',
        'cases.caseexport.*',
        'cases.partner.*',

        'contacts.contact_read',
        'contacts.group.*',
        'contacts.field.*',

        'profiles.profile.*',

        'rules.rule.*',

        'statistics.dailycountexport.*',
    ),
    "Editors": (  # Partner users: Managers
        'orgs.org_inbox',
        'orgs.org_charts',

        'msgs.label_read',
        'msgs.message_action',
        'msgs.message_bulk_reply',
        'msgs.message_forward',
        'msgs.message_history',
        'msgs.message_label',
        'msgs.message_search',
        'msgs.messageexport_create',
        'msgs.messageexport_read',
        'msgs.outgoing_search',
        'msgs.outgoing_search_replies',
        'msgs.replyexport_create',
        'msgs.replyexport_read',

        'cases.case_create',
        'cases.case_read',
        'cases.case_update',
        'cases.case_list',
        'cases.case_replies',
        'cases.caseexport_create',
        'cases.caseexport_read',
        'cases.partner_list',
        'cases.partner_read',

        'contacts.contact_read',

        'profiles.profile_user_create_in',
        'profiles.profile_user_update',
        'profiles.profile_user_read',
        'profiles.profile_user_list',
    ),
    "Viewers": (  # Partner users: Data Analysts
        'orgs.org_inbox',
        'orgs.org_charts',

        'msgs.label_read',
        'msgs.message_action',
        'msgs.message_bulk_reply',
        'msgs.message_forward',
        'msgs.message_history',
        'msgs.message_label',
        'msgs.message_search',
        'msgs.messageexport_create',
        'msgs.messageexport_read',
        'msgs.outgoing_search',
        'msgs.outgoing_search_replies',
        'msgs.replyexport_create',
        'msgs.replyexport_read',

        'cases.case_create',
        'cases.case_read',
        'cases.case_update',
        'cases.case_list',
        'cases.case_replies',
        'cases.caseexport_create',
        'cases.caseexport_read',
        'cases.partner_list',
        'cases.partner_read',

        'contacts.contact_read',

        'profiles.profile_user_read',
        'profiles.profile_user_list',
    ),
}

# -----------------------------------------------------------------------------------
# Login / Logout
# -----------------------------------------------------------------------------------
LOGIN_URL = "/users/login/"
LOGOUT_URL = "/users/logout/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

ANONYMOUS_USER_ID = -1

# -----------------------------------------------------------------------------------
# Debug Toolbar
# -----------------------------------------------------------------------------------

INTERNAL_IPS = ('127.0.0.1',)

# -----------------------------------------------------------------------------------
# Django-celery
# -----------------------------------------------------------------------------------
djcelery.setup_loader()

BROKER_URL = 'redis://localhost:6379/%d' % (10 if TESTING else 15)
CELERY_RESULT_BACKEND = BROKER_URL

CELERYBEAT_SCHEDULE = {
    'message-pull': {
        'task': 'dash.orgs.tasks.trigger_org_task',
        'schedule': timedelta(minutes=1),
        'args': ('casepro.msgs.tasks.pull_messages', 'sync')
    },
    'contact-pull': {
        'task': 'dash.orgs.tasks.trigger_org_task',
        'schedule': timedelta(minutes=3),
        'args': ('casepro.contacts.tasks.pull_contacts', 'sync')
    },
    'message-handle': {
        'task': 'dash.orgs.tasks.trigger_org_task',
        'schedule': timedelta(minutes=1),
        'args': ('casepro.msgs.tasks.handle_messages', 'sync')
    },
    'squash-label-counts': {
        'task': 'casepro.msgs.tasks.squash_counts',
        'schedule': timedelta(minutes=5),
    },
    'squash-stat-counts': {
        'task': 'casepro.statistics.tasks.squash_counts',
        'schedule': timedelta(minutes=5),
    },
    'send-notifications': {
        'task': 'casepro.profiles.tasks.send_notifications',
        'schedule': timedelta(minutes=1),
    },
}

CELERY_TIMEZONE = 'UTC'
