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

