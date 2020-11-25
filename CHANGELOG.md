v1.3.13
----------
 * Add SecurityMiddleware to common settings

v1.3.12
----------
 * Fix XSS vulnerablilities in rules template tags
 * Add management command for summarizing usage stats across orgs
 * Bump pillow version

v1.3.11
----------
 * Fix wrong arg name for latest rapidpro client

v1.3.10
----------
 * Update to latest rapidpro-python

v1.3.9
----------
 * Fix reply view when org has replies without reply_to set

v1.3.8
----------
 * Add autocomplete=off to login page
 * Remove novalidate on forms

v1.3.7
----------
 * Upgrade to latest bootstrap 3.3.x
 * Only allow CSV file extensions for FAQ imports
 * Fix embedding of JSON in templates
 * Only allow partners users to view users in same partner org
 * Require current password when user changes their password

v1.3.5
----------
 * Make password requirements stricter

v1.3.4
----------
 * Fix unrelated failing test due to ordering of labels
 * Fix styling on partner update/create forms and add validator for image file extensions
 * Update to jQuery 1.11.3

v1.3.3
----------
 * Add XFrameOptionsMiddleware
 * Tweak notifications for re-assigned cases so if assignee is specific user, only they get notified

v1.3.2
----------
 * Revert upgrade to django-storages

v1.3.1
----------
 * Update to latest angular 1.4.x

v1.3.0
----------
 * Fix editing of must_use_faq
 * If case is assigned to specific user, only notify that user
 * Show contact name on open case modal
 * Add tab to user page which lists cases assigned to them
 * Bump to latest minor release for all deps

v1.2.7
----------
 * Fix translation

v1.2.6
----------
 * Add spanish translations from transifex

v1.2.5
----------
 * Minor dependency updates
 * Tidy up translatable strings with trimmed
 * Add code_check script and generate locale files for Spanish

v1.2.4
----------
 * Bump django from 2.2.8 to 2.2.10

v1.2.3
----------
 * Fix another case of filter getting duplicate keyword arguments

v1.2.2
----------
 * Fix searching by text and date

v1.2.1
----------
 * Limit searching by text to the last 90 days

v1.2.0
----------
 * Add charts for cases opened and closed
 * Drop pod support

v1.1.28
----------
 * Add link to rules list page on org summary
 * Improve rules list page

v1.1.27
----------
 * Render label rule tests on read page

v1.1.26
----------
 * Allow rules without keywords

v1.1.25
----------
 * Rework message searching to use new fields on labelling

v1.1.24
----------
 * Make message fields on labelling m2m no-null and add indexes

v1.1.23
----------
 * Migration to backfill new fields on msgs_message_labels

v1.1.22
----------
 * Add message fields to labelling m2m

v1.1.21
----------
 * Simplify Message.search
 * Add pre/post commit hooks
 * Add management command to create test database

v1.1.20
----------
 * Switch squashing to use is_squashed instead of redis key
 * Add new partial indexes on squashable models

v1.1.19
----------
 * Update database triggers for counts

v1.1.18
----------
 * Add migration to backfill is_squashed on squashable models

v1.1.17
----------
 * Add is_squashed field to squashable models
 * Bump dependencies
 * Switch CI tests to PG 10/11 and use github actions and codecov for coverage

v1.1.16
----------
 * Don't create a rule for a label if there are no keywords set
 * Bump some dependencies

v1.1.15
----------
 * Log long message queries

v1.1.14
----------
 * Include messages received after initial msg in case

v1.1.13
----------
 * Actions should still succeed even if their backend operations fail (log that to sentry)
 * Fix load label permissions

v1.1.12
----------
 * Latest dash

v1.1.11
----------
 * Refresh label counts after applying labels to messages

v1.1.10
----------
 * Upgrade to last rapidpro client

v1.1.9
----------
 * Extra logging in contact sync task

v1.1.8
----------
 * Update all dependencies

v1.1.7
----------
 * Ensure new orgs are created with a backend

v1.1.6
----------
 * Fix not clearing follow-up flows

v1.1.5
----------
 * Make followup flow optional

v1.1.4
----------
 * Add support for followup flows which can be triggered when a case is closed

v1.1.3
----------
 * Switch to using cursor pagination in the API

v1.1.2
----------
 * Add labels API endpoint, bnew fields to cases endpoint, improve API docs
 * Use new index on CaseAction.org in API requests
 * Make CaseAction.org non-null and add index

v1.1.1
----------
 * Migration to backfill CaseAction.org

v1.1.0
----------
 * Add org field to CaseAction
 * Add basic API
 * Dpendency update and cleanup

v1.0.2
----------
 * Upgrade to Django 2
 * Fix not saving change_password when updating a user

v1.0.1
----------
 * Import orgbackend CRUDL from dash

v1.0.0
----------
 * Code formatting with black+isort
 * Update to sorl-thumbnail 12.4.1
 * Drop support for Python 2
 * Update rapidpro-dash to 1.3.4

v0.0.259
----------
 * Update to latest Django
 * Don't allow label names which are invalid in RapidPro
 * Remove searching by group - this should be done by labelling by group which we can actually optimize
 * Fixes to language migration

v0.0.258
----------
 * Migrate languages from ISO639-2 to ISO639-3

v0.0.257
----------
 * Fix fetching of modified and new messages

v0.0.256
----------
 * Increase max infinite scroll items to 2000

v0.0.255
----------
 * Fix fields not being listed on label edit form

v0.0.254
----------
 * Use BigInt primary keys on squashable models
 * Add portuguese as supported languages

v0.0.253
----------
 * Don't try to restore contacts into their groups if they are now stopped or blocked

v0.0.252
----------
 * Fix new item polling in inbox controller 

v0.0.251
----------
 * Start using modified_on to fetch messages that have been acted on or locked

v0.0.250
----------
 * Add index on Message.modified_on (large deployments should fake this and add manually with CONCURRENTLY)

v0.0.249
----------
 * Add Message.modified_on field and start populating it for new messages

v0.0.248
----------
 * Update to latest django, dash and smartmin

v0.0.247
----------
 * Python 3.6 support
 * Switch DailySecondCount.seconds field to big integer to avoid overflow

v0.0.246
----------
 * delete personal info on Junebug optout

v0.0.245
----------
 * Inbox refreshing and message locking
 * Django 1.10 fix

v0.0.244
----------
 * Increase default maximum message length to 160

v0.0.243
----------
 * Add CHANGELOG.md
 * Fix field test blowing up if contact.fields is null
 * Remove no longer needed compress.py
 * Update to latest smartmin
 * Disable less and coffeescript compilation during unit tests to improve test performance
 * Don't have celery store task results as these are modelled internally

