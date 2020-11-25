import os
import sys
from datetime import timedelta

from django.utils.translation import ugettext_lazy as _

# -----------------------------------------------------------------------------------
# Sets TESTING to True if this configuration is read during a unit test
# -----------------------------------------------------------------------------------
TESTING = sys.argv[1:2] == ["test"]

if TESTING:
    PASSWORD_HASHERS = ("django.contrib.auth.hashers.MD5PasswordHasher",)
    DEBUG = False
else:
    DEBUG = True

ADMINS = (("Nyaruka", "code@nyaruka.com"),)

MANAGERS = ADMINS

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "casepro.sqlite",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}

EMAIL_BACKEND = "djcelery_email.backends.CeleryEmailBackend"
SEND_EMAILS = TESTING  # safe to send emails during tests as these use a fake backend

# dash configuration
SITE_API_HOST = "http://localhost:8001/"
SITE_API_USER_AGENT = "casepro/0.1"
SITE_HOST_PATTERN = "http://%s.localhost:8000"
SITE_CHOOSER_URL_NAME = "orgs_ext.org_chooser"
SITE_CHOOSER_TEMPLATE = "org_chooser.haml"
SITE_USER_HOME = "/"
SITE_ALLOW_NO_ORG = (
    "orgs_ext.org_create",
    "orgs_ext.org_update",
    "orgs_ext.org_list",
    "orgs_ext.task_list",
    "profiles.user_create",
    "profiles.user_update",
    "profiles.user_read",
    "profiles.user_list",
    "internal.status",
    "internal.ping",
)

# casepro configuration
SITE_ORGS_STORAGE_ROOT = "orgs"
SITE_EXTERNAL_CONTACT_URL = "http://localhost:8001/contact/read/%s/"
SITE_BACKEND = "casepro.backend.NoopBackend"
SITE_HIDE_CONTACT_FIELDS = []  # Listed fields should not be displayed
SITE_CONTACT_DISPLAY = "name"  # Overrules SITE_HIDE_CONTACT_FIELDS Options: 'name', 'uuid' or 'urns'
SITE_ALLOW_CASE_WITHOUT_MESSAGE = True
SITE_MAX_MESSAGE_CHARS = 160  # the max value for this is 800

# junebug configuration
JUNEBUG_API_ROOT = "http://localhost:8080/"
JUNEBUG_INBOUND_URL = r"^junebug/inbound$"
JUNEBUG_CHANNEL_ID = "replace-me"
JUNEBUG_FROM_ADDRESS = None

JUNEBUG_HUB_BASE_URL = None
JUNEBUG_HUB_AUTH_TOKEN = None

# identity store configuration
IDENTITY_API_ROOT = "http://localhost:8081/"
IDENTITY_AUTH_TOKEN = "replace-with-auth-token"
IDENTITY_ADDRESS_TYPE = "msisdn"
IDENTITY_STORE_OPTOUT_URL = r"^junebug/optout$"
IDENTITY_LANGUAGE_FIELD = "language"

# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone
TIME_ZONE = "GMT"
USER_TIME_ZONE = "GMT"
USE_TZ = True

SITE_DATE_FORMAT = r"%b %d, %Y"

MODELTRANSLATION_TRANSLATION_REGISTRY = "translation"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en"

# Available languages for translation
LANGUAGES = (("en", _("English")), ("fr", _("French")), ("pt-br", _("Portuguese")), ("es", _("Spanish")))
RTL_LANGUAGES = {}
DEFAULT_LANGUAGE = "en"

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "/sitestatic/"
COMPRESS_URL = "/sitestatic/"

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = "/sitestatic/admin/"

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = "4-rr2sa6c#5*vr^2$m*2*j+5tc9duo2q+5e!xra%n($d5a$yp)"

MIDDLEWARE = (
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "dash.orgs.middleware.SetOrgMiddleware",
    "casepro.utils.middleware.JSONMiddleware",
    "casepro.profiles.middleware.ForcePasswordChangeMiddleware",
)

ROOT_URLCONF = "casepro.urls"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/15",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}


DATA_API_BACKEND_TYPES = (("casepro.backend.rapidpro.RapidProBackend", "RapidPro Backend Type"),)

ORG_CONFIG_FIELDS = [
    dict(name="contact_fields", field=dict(help_text=_("Contact fields to display"), required=False)),
    dict(name="banner_text", field=dict(help_text=_("Banner text displayed to all users"), required=False)),
]

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "django_comments",
    "djcelery_email",
    "compressor",
    "sorl.thumbnail",
    "hamlpy",
    "rest_framework",
    "rest_framework.authtoken",
    "smartmin",
    "smartmin.csv_imports",
    "smartmin.users",
    "dash.orgs",
    "dash.utils",
    "casepro.orgs_ext",
    "casepro.profiles",
    "casepro.contacts",
    "casepro.msgs",
    "casepro.msg_board",
    "casepro.rules",
    "casepro.cases",
    "casepro.statistics",
    "casepro.api",
)

COMMENTS_APP = "casepro.msg_board"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s"},
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "console": {"level": "DEBUG", "class": "logging.StreamHandler", "formatter": "verbose"},
        "null": {"class": "logging.NullHandler"},
    },
    "loggers": {
        "httprouterthread": {"handlers": ["console"], "level": "INFO"},
        "django.request": {"handlers": ["console"], "level": "ERROR"},
        "django.db.backends": {"level": "ERROR", "handlers": ["console"], "propagate": False},
        "django.security.DisallowedHost": {"handlers": ["null"], "propagate": False},
    },
}

# -----------------------------------------------------------------------------------
# Directory Configuration
# -----------------------------------------------------------------------------------
PROJECT_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)))

LOCALE_PATHS = (os.path.join(PROJECT_DIR, "../locale"),)
RESOURCES_DIR = os.path.join(PROJECT_DIR, "../resources")
FIXTURE_DIRS = (os.path.join(PROJECT_DIR, "../fixtures"),)
TESTFILES_DIR = os.path.join(PROJECT_DIR, "../testfiles")
STATICFILES_DIRS = (os.path.join(PROJECT_DIR, "../static"), os.path.join(PROJECT_DIR, "../media"))
STATIC_ROOT = os.path.join(PROJECT_DIR, "../sitestatic")
MEDIA_ROOT = os.path.join(PROJECT_DIR, "../media")
MEDIA_URL = "/media/"

# -----------------------------------------------------------------------------------
# Templates Configuration
# -----------------------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(PROJECT_DIR, "../templates")],
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
                "dash.orgs.context_processors.user_group_perms_processor",
                "dash.orgs.context_processors.set_org_processor",
                "dash.context_processors.lang_direction",
                "casepro.cases.context_processors.sentry_dsn",
                "casepro.cases.context_processors.server_time",
                "casepro.profiles.context_processors.user",
                "casepro.msgs.context_processors.messages",
            ],
            "loaders": [
                "dash.utils.haml.HamlFilesystemLoader",
                "dash.utils.haml.HamlAppDirectoriesLoader",
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "debug": False if TESTING else DEBUG,
        },
    }
]

# -----------------------------------------------------------------------------------
# Permission Management
# -----------------------------------------------------------------------------------

# this lets us easily create new permissions across our objects
PERMISSIONS = {
    "*": (
        "create",  # can create an object
        "read",  # can read an object, viewing it's details
        "update",  # can update an object
        "delete",  # can delete an object,
        "list",
    ),  # can view a list of the objects
    "orgs.org": ("create", "update", "list", "home", "edit", "inbox", "charts"),
    "msgs.label": ("create", "update", "read", "delete", "list"),
    "msgs.faq": ("create", "read", "update", "delete", "list", "search", "import", "languages"),
    "msgs.message": ("action", "bulk_reply", "forward", "label", "history", "search", "unlabelled", "lock"),
    "msgs.messageexport": ("create", "read"),
    "msgs.outgoing": ("search", "search_replies"),
    "msgs.replyexport": ("create", "read"),
    "cases.case": ("create", "read", "update", "list"),
    "case.caseexport": ("create", "read"),
    "cases.partner": ("create", "read", "delete", "list"),
    "contacts.contact": ("read", "list"),
    "contacts.group": ("select", "list"),
    "msg_board.messageboardcomment": ("list", "pinned", "pin", "unpin"),
    # can't create profiles.user.* permissions because we don't own User
    "profiles.profile": ("user_create", "user_create_in", "user_update", "user_read", "user_list"),
}

# assigns the permissions that each group should have
GROUP_PERMISSIONS = {
    "Administrators": (  # Org users: Administrators
        "orgs.org_inbox",
        "orgs.org_home",
        "orgs.org_charts",
        "orgs.org_edit",
        "csv_imports.importtask.*",
        "msgs.label.*",
        "msgs.faq.*",
        "msgs.message.*",
        "msgs.messageexport.*",
        "msgs.outgoing.*",
        "msgs.replyexport.*",
        "cases.case.*",
        "cases.caseexport.*",
        "cases.partner.*",
        "contacts.contact_read",
        "contacts.group.*",
        "contacts.field.*",
        "profiles.profile.*",
        "rules.rule.*",
        "statistics.dailycountexport.*",
        "msg_board.messageboardcomment.*",
    ),
    "Editors": (  # Partner users: Managers
        "orgs.org_inbox",
        "orgs.org_charts",
        "msgs.label_read",
        "msgs.label_list",
        "msgs.faq_search",
        "msgs.faq_languages",
        "msgs.message_action",
        "msgs.message_bulk_reply",
        "msgs.message_forward",
        "msgs.message_history",
        "msgs.message_label",
        "msgs.message_search",
        "msgs.message_lock",
        "msgs.messageexport_create",
        "msgs.messageexport_read",
        "msgs.outgoing_search",
        "msgs.outgoing_search_replies",
        "msgs.replyexport_create",
        "msgs.replyexport_read",
        "cases.case_create",
        "cases.case_read",
        "cases.case_update",
        "cases.case_list",
        "cases.case_replies",
        "cases.caseexport_create",
        "cases.caseexport_read",
        "cases.partner_list",
        "cases.partner_read",
        "contacts.contact_read",
        "profiles.profile_user_create_in",
        "profiles.profile_user_update",
        "profiles.profile_user_read",
        "profiles.profile_user_list",
        "msg_board.messageboardcomment.*",
    ),
    "Viewers": (  # Partner users: Data Analysts
        "orgs.org_inbox",
        "orgs.org_charts",
        "msgs.faq_search",
        "msgs.faq_languages",
        "msgs.label_read",
        "msgs.label_list",
        "msgs.message_action",
        "msgs.message_bulk_reply",
        "msgs.message_forward",
        "msgs.message_history",
        "msgs.message_label",
        "msgs.message_search",
        "msgs.message_lock",
        "msgs.messageexport_create",
        "msgs.messageexport_read",
        "msgs.outgoing_search",
        "msgs.outgoing_search_replies",
        "msgs.replyexport_create",
        "msgs.replyexport_read",
        "cases.case_create",
        "cases.case_read",
        "cases.case_update",
        "cases.case_list",
        "cases.case_replies",
        "cases.caseexport_create",
        "cases.caseexport_read",
        "cases.partner_list",
        "cases.partner_read",
        "contacts.contact_read",
        "profiles.profile_user_read",
        "profiles.profile_user_list",
        "msg_board.messageboardcomment.*",
    ),
}

# -----------------------------------------------------------------------------------
# Login / Logout
# -----------------------------------------------------------------------------------
LOGIN_URL = "/users/login/"
LOGOUT_URL = "/users/logout/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS = ("smartmin.backends.CaseInsensitiveBackend",)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------------------------------------------------------------
# Debug Toolbar
# -----------------------------------------------------------------------------------

INTERNAL_IPS = ("127.0.0.1",)

# -----------------------------------------------------------------------------------
# Django-celery
# -----------------------------------------------------------------------------------
BROKER_URL = "redis://localhost:6379/%d" % (10 if TESTING else 15)
CELERY_RESULT_BACKEND = None  # task results are stored internally

CELERYBEAT_SCHEDULE = {
    "message-pull": {
        "task": "dash.orgs.tasks.trigger_org_task",
        "schedule": timedelta(minutes=1),
        "args": ("casepro.msgs.tasks.pull_messages", "sync"),
    },
    "contact-pull": {
        "task": "dash.orgs.tasks.trigger_org_task",
        "schedule": timedelta(minutes=3),
        "args": ("casepro.contacts.tasks.pull_contacts", "sync"),
    },
    "message-handle": {
        "task": "dash.orgs.tasks.trigger_org_task",
        "schedule": timedelta(minutes=1),
        "args": ("casepro.msgs.tasks.handle_messages", "sync"),
    },
    "squash-counts": {"task": "casepro.statistics.tasks.squash_counts", "schedule": timedelta(minutes=5)},
    "send-notifications": {"task": "casepro.profiles.tasks.send_notifications", "schedule": timedelta(minutes=1)},
}

CELERY_TIMEZONE = "UTC"

# -----------------------------------------------------------------------------------
# Django Compressor configuration
# -----------------------------------------------------------------------------------

if TESTING:
    # if only testing, disable coffeescript and less compilation
    COMPRESS_PRECOMPILERS = ()
else:
    COMPRESS_PRECOMPILERS = (
        ("text/less", 'lessc --include-path="%s" {infile} {outfile}' % os.path.join(PROJECT_DIR, "../static", "less")),
        ("text/coffeescript", "coffee --compile --stdio"),
    )
    COMPRESS_OFFLINE_CONTEXT = dict(STATIC_URL=STATIC_URL, base_template="frame.html")

# -----------------------------------------------------------------------------------
# REST API
# -----------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("casepro.api.support.AdministratorPermission",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 100,
}
