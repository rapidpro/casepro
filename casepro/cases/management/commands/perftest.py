import time
from collections import namedtuple
from importlib import import_module

from colorama import Fore, Style
from colorama import init as colorama_init
from dash.orgs.models import Org
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.db import connection, reset_queries
from django.http import HttpRequest
from django.test.client import Client

Problem = namedtuple("Problem", ["test", "org", "partner", "user", "time"])

REQUEST_TIME_LIMITS = (0.5, 1)  # limit for warning, limit for problem
DB_TIME_LIMITS = (0.5, 1)
NUM_QUERY_LIMITS = (50, 100)
NUM_REQUESTS = 3  # number of requests made per view


VIEW_TESTS = (
    ("msgs.message_search", "?folder=inbox&archived=0&page=1"),
    ("msgs.message_search", "?folder=archived&page=1"),
    ("msgs.message_search", "?folder=flagged&page=1"),
    ("msgs.outgoing_search", "?folder=sent&page=1"),
    ("msgs.outgoing_search_replies", "?page=1"),
    ("cases.case_search", "?folder=open&page=1"),
    ("cases.case_search", "?folder=closed&page=1"),
)


class Command(BaseCommand):
    help = "Checks performance of inbox view for all partners"
    verbose = False

    def handle(self, *args, **options):
        self.verbose = options["verbosity"] >= 2

        colorama_init()

        settings.COMPRESS_ENABLED = True

        problems = []

        for org in Org.objects.filter(is_active=True).order_by("name"):
            self.log("Checking view performance for org '%s'..." % org.name)
            self.log(" > Checking as admin user...")

            admin = org.administrators.first()
            problems += self.test_as_user(org, None, admin)

            for partner in org.partners.order_by("name"):
                restriction = "%d labels" % partner.get_labels().count() if partner.is_restricted else "unrestricted"

                self.log(" > Checking as user in partner '%s' (%s)..." % (partner.name, restriction))

                # find a suitable user in this partner
                user = User.objects.filter(profile__partner=partner, profile__change_password=False).first()
                if user:
                    problems += self.test_as_user(org, partner, user)
                else:
                    self.log("    - No suitable user found (skipping)")

        self.stdout.write("Problems...")

        for problem in sorted(problems, key=lambda p: p.time, reverse=True):
            view_name, query_string = problem.test
            url = reverse(view_name) + query_string

            self.stdout.write(
                " > %s %s secs (org='%s', partner='%s')"
                % (
                    colored(url, Fore.BLUE),
                    colorcoded(problem.time, REQUEST_TIME_LIMITS),
                    problem.org.name,
                    problem.partner.name if problem.partner else "",
                )
            )

    def test_as_user(self, org, partner, user):
        problems = []
        for test in VIEW_TESTS:
            view_name, query_string = test
            request_time = self.test_view(user, org.subdomain, view_name, query_string, NUM_REQUESTS)

            if request_time > REQUEST_TIME_LIMITS[1]:
                problems.append(Problem(test, org, partner, user, request_time))
        return problems

    def test_view(self, user, subdomain, view_name, query_string, num_requests):
        url = reverse(view_name) + query_string

        client = DjangoClient()
        client.force_login(user)

        statuses = []
        request_times = []
        db_times = []
        query_counts = []

        for r in range(num_requests):
            reset_queries()
            start_time = time.time()

            response = client.get(url, HTTP_HOST="%s.localhost" % subdomain)

            statuses.append(response.status_code)
            request_times.append(time.time() - start_time)
            db_times.append(sum([float(q["time"]) for q in connection.queries]))
            query_counts.append(len(connection.queries))

        last_status = statuses[-1]
        avg_request_time = sum(request_times) / len(request_times)
        avg_db_time = sum(db_times) / len(db_times)
        last_query_count = query_counts[-1]

        self.log(
            "    - %s %s %s secs (db=%s secs, queries=%s)"
            % (
                colored(url, Fore.BLUE),
                colored(last_status, Fore.GREEN if 200 <= last_status < 300 else Fore.RED),
                colorcoded(avg_request_time, REQUEST_TIME_LIMITS),
                colorcoded(avg_db_time, DB_TIME_LIMITS),
                colorcoded(last_query_count, NUM_QUERY_LIMITS),
            )
        )

        return avg_request_time

    def log(self, message):
        if self.verbose:
            self.stdout.write(message)


def colorcoded(val, limits):
    if val > limits[1]:
        color = Fore.RED
    elif val > limits[0]:
        color = Fore.YELLOW
    else:
        color = Fore.GREEN

    if isinstance(val, float):
        val = "%.3f" % val

    return colored(val, color)


def colored(val, color):
    return color + str(val) + Fore.RESET


def styled(val, style):
    return style + str(val) + Style.RESET_ALL


class DjangoClient(Client):
    """
    Until we upgrade to Django 1.9, provides a test client with force_login for easy access as different users
    """

    def login(self, **credentials):
        """
        Sets the Factory to appear as if it has successfully logged into a site.

        Returns True if login is possible; False if the provided credentials
        are incorrect, or the user is inactive, or if the sessions framework is
        not available.
        """
        from django.contrib.auth import authenticate

        user = authenticate(**credentials)
        if user and user.is_active:
            self._login(user)
            return True
        else:
            return False

    def force_login(self, user, backend=None):
        if backend is None:
            backend = settings.AUTHENTICATION_BACKENDS[0]
        user.backend = backend
        self._login(user)

    def _login(self, user):
        from django.contrib.auth import login

        engine = import_module(settings.SESSION_ENGINE)

        # Create a fake request to store login details.
        request = HttpRequest()

        if self.session:
            request.session = self.session
        else:
            request.session = engine.SessionStore()
        login(request, user)

        # Save the session values.
        request.session.save()

        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        self.cookies[session_cookie] = request.session.session_key
        cookie_data = {
            "max-age": None,
            "path": "/",
            "domain": settings.SESSION_COOKIE_DOMAIN,
            "secure": settings.SESSION_COOKIE_SECURE or None,
            "expires": None,
        }
        self.cookies[session_cookie].update(cookie_data)
