#============================================================================
# Application services
#============================================================================

services = angular.module('cases.services', ['cases.modals']);


DEFAULT_POST_OPTS = {transformRequest: angular.identity, headers: {'Content-Type': undefined}}

DEFAULT_ERR_HANDLER = (data, status, headers, config) =>
  console.error("Request error (status = " + status + ")")

#=====================================================================
# Utilities
#=====================================================================

parseIso8601 = (str) ->
  if str then new Date(Date.parse str) else null

formatIso8601 = (date) ->
  if date then date.toISOString() else null

isArray = Array.isArray || (val) -> return {}.toString.call(val) is '[object Array]'

toFormData = (params) ->
  data = new FormData()
  for own key, val of params
    if isArray(val)
      val = (item.toString() for item in val).join(',')
    else if val
      val = val.toString()  # required for https://bugzilla.mozilla.org/show_bug.cgi?id=819328

    if val
      data.append(key, val)

  return data

#=====================================================================
# Incoming message service
#=====================================================================

services.factory 'MessageService', ['$rootScope', '$http', ($rootScope, $http) ->
  new class MessageService

    #----------------------------------------------------------------------------
    # Fetches old messages for the given search
    #----------------------------------------------------------------------------
    fetchOld: (search, before, page, callback) ->
      params = @_searchToParams(search)
      if !search.before
        params.before = formatIso8601(before)
      params.page = page

      $http.get('/message/search/?' + $.param(params))
      .success((data) =>
        @_processMessages(data.results)

        console.log("Fetched " + data.results.length + " old messages")

        callback(data.results, data.has_more)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Fetches new messages for the given search
    #----------------------------------------------------------------------------
    fetchNew: (search, after, before, callback) ->
      params = @_searchToParams(search)
      params.after = formatIso8601(after)
      params.before = formatIso8601(before)

      $http.get('/message/?' + $.param(params))
      .success((data) =>
        @_processMessages(data.results)

        if data.results.length > 0
          maxTime = data.results[0].time
          maxId = data.results[0].id
        else
          maxTime = null
          maxId = null

        callback(data.results, maxTime, maxId)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Fetches history for a single message
    #----------------------------------------------------------------------------
    fetchHistory: (message, callback) ->
      $http.get('/message/history/' + message.id + '/')
      .success((data) =>
        @_processMessageActions(data.actions)
        callback(data.actions)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Starts a message export
    #----------------------------------------------------------------------------
    startExport: (search, callback) ->
      params = @_searchToParams(search)
      $http.post('/messageexport/create/?' + $.param(params))
      .success(() =>
        callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Reply-to messages
    #----------------------------------------------------------------------------
    replyToMessages: (messages, text, callback) ->
      params = {
        text: text,
        messages: (m.id for m in messages)
      }

      $http.post('/message/bulk_reply/', toFormData(params), DEFAULT_POST_OPTS)
      .success((data) =>
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Flag or un-flag messages
    #----------------------------------------------------------------------------
    flagMessages: (messages, flagged, callback) ->
      action = if flagged then 'flag' else 'unflag'
      @_messagesAction(messages, action, null, () ->
        for msg in messages
          msg.flagged = flagged
        if callback
          callback()
      )

    #----------------------------------------------------------------------------
    # Label messages with the given label
    #----------------------------------------------------------------------------
    labelMessages: (messages, label, callback) ->
      without_label = []
      for msg in messages
        if label.name not in msg.labels
          without_label.push(msg)
          msg.labels.push(label)

      if without_label.length > 0
        @_messagesAction(without_label, 'label', label, callback)

    #----------------------------------------------------------------------------
    # Archive messages
    #----------------------------------------------------------------------------
    archiveMessages: (messages, callback) ->
      @_messagesAction(messages, 'archive', null, () ->
        for msg in messages
          msg.archived = true
        if callback
          callback()
      )

    #----------------------------------------------------------------------------
    # Restore (i.e. un-archive) messages
    #----------------------------------------------------------------------------
    restoreMessages: (messages, callback) ->
      @_messagesAction(messages, 'restore', null, () ->
        for msg in messages
          msg.archived = false
        if callback
          callback()
      )

    #----------------------------------------------------------------------------
    # Relabel the given message (removing labels if necessary)
    #----------------------------------------------------------------------------
    relabelMessage: (message, labels, callback) ->
      data = toFormData({
        labels: (l.id for l in labels)
      })

      $http.post('/message/label/' + message.id + '/', data, DEFAULT_POST_OPTS)
      .success(() ->
        message.labels = labels
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Forward a message to a URN
    #----------------------------------------------------------------------------
    forwardMessage: (message, text, urn, callback) ->
      params = {
        text: text,
        urns: [urn.urn]
      }

      $http.post('/message/forward/' + message.id + '/', toFormData(params), DEFAULT_POST_OPTS)
      .success((data) =>
        callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Convert search object to URL params
    #----------------------------------------------------------------------------
    _searchToParams: (search) ->
      return {
        folder: search.folder,
        text: search.text,
        after: formatIso8601(search.after),
        before: formatIso8601(search.before),
        groups: (g.uuid for g in search.groups).join(','),
        contact: if search.contact then search.contact.uuid else null,
        label: if search.label then search.label.id else null,
        archived: if search.archived then 1 else 0
      }

    #----------------------------------------------------------------------------
    # POSTs to the messages action endpoint
    #----------------------------------------------------------------------------
    _messagesAction: (messages, action, label, callback) ->
      params = {
        messages: (m.id for m in messages)
      }
      if label
        params.label = label.id

      $http.post('/message/action/' + action + '/', toFormData(params), DEFAULT_POST_OPTS)
      .success(() =>
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Processes incoming messages
    #----------------------------------------------------------------------------
    _processMessages: (messages) ->
      for msg in messages
        msg.time = parseIso8601(msg.time)  # parse datetime string

    #----------------------------------------------------------------------------
    # Processes incoming message actions
    #----------------------------------------------------------------------------
    _processMessageActions: (actions) ->
      for action in actions
        action.created_on = parseIso8601(action.created_on)  # parse datetime string
]


#=====================================================================
# Incoming message service
#=====================================================================

services.factory 'OutgoingService', ['$rootScope', '$http', ($rootScope, $http) ->
  new class OutgoingService

    #----------------------------------------------------------------------------
    # Fetches old outgoing messages for the given search
    #----------------------------------------------------------------------------
    fetchOld: (search, startTime, page, callback) ->
      params = @_outboxSearchToParams(search, startTime, page)

      $http.get('/outgoing/search/?' + $.param(params))
      .success((data) =>
        callback(data.results, data.has_more)
      ).error(DEFAULT_ERR_HANDLER)

    fetchReplies: (search, startTime, page, callback) ->
      params = @_replySearchToParams(search, startTime, page)

      $http.get('/outgoing/search_replies/?' + $.param(params))
      .success((data) =>
        callback(data.results, data.has_more)
      ).error(DEFAULT_ERR_HANDLER)

    startReplyExport: (search, callback) ->
      params = @_replySearchToParams(search, null, null)

      $http.get('/replyexport/create/?' + $.param(params))
      .success((data) =>
        callback(data.results, data.has_more)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Convert a regular outbox search object to URL params
    #----------------------------------------------------------------------------
    _outboxSearchToParams: (search, startTime, page) ->
      return {
        folder: search.folder,
        text: search.text,
        contact: if search.contact then search.contact.uuid else null,
        before: formatIso8601(startTime),
        page: page
      }

    #----------------------------------------------------------------------------
    # Convert a reply search object to URL params
    #----------------------------------------------------------------------------
    _replySearchToParams: (search, startTime, page) ->
      return {
        partner: search.partner.id,
        after: formatIso8601(search.after),
        before: if search.before then formatIso8601(search.before) else formatIso8601(startTime),
        page: page
      }
]


#=====================================================================
# Label service
#=====================================================================

services.factory 'LabelService', ['$http', ($http) ->
  new class LabelService

    #----------------------------------------------------------------------------
    # Deletes a label
    #----------------------------------------------------------------------------
    deleteLabel: (label, callback) ->
      $http.post('/label/delete/' + label.id + '/')
      .success(() ->
        callback()
      ).error(DEFAULT_ERR_HANDLER)
]


#=====================================================================
# Case service
#=====================================================================

services.factory 'CaseService', ['$http', '$window', ($http, $window) ->
  new class CaseService

    #----------------------------------------------------------------------------
    # Fetches old cases
    #----------------------------------------------------------------------------
    fetchOld: (search, before, page, callback) ->
      params = @_searchToParams(search)
      params.before = formatIso8601(before)
      params.page = page

      $http.get('/case/search/?' + $.param(params))
      .success((data) =>
        @_processCases(data.results)
        callback(data.results, data.has_more)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Fetches new cases
    #----------------------------------------------------------------------------
    fetchNew: (search, after, before, callback) ->
      params = @_searchToParams(search)
      params.after = formatIso8601(after)
      params.before = formatIso8601(before)

      $http.get('/case/search/?' + $.param(params))
      .success((data) =>
        @_processCases(data.results)
        callback(data.results)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Fetches an existing case by it's id
    #----------------------------------------------------------------------------
    fetchCase: (caseId, callback) ->
      $http.get('/case/fetch/' + caseId + '/')
      .success((caseObj) =>
        @_processCases([caseObj])
        callback(caseObj)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Starts a case export
    #----------------------------------------------------------------------------
    startExport: (search, callback) ->
      params = @_searchToParams(search)
      $http.post('/caseexport/create/?' + $.param(params))
      .success(() =>
        callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Opens a new case
    #----------------------------------------------------------------------------
    openCase: (message, summary, assignee, callback) ->
      params = {
        message: message.id,
        summary: summary
      }
      if assignee
        params.assignee = assignee.id

      $http.post('/case/open/', toFormData(params), DEFAULT_POST_OPTS)
      .success((data) ->
        callback(data['case'], data['is_new'])
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Adds a note to a case
    #----------------------------------------------------------------------------
    noteCase: (caseObj, note, callback) ->
      params = {note: note}

      $http.post('/case/note/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS)
      .success(() ->
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Re-assigns a case
    #----------------------------------------------------------------------------
    reassignCase: (caseObj, assignee, callback) ->
      params = {assignee: assignee.id}

      $http.post('/case/reassign/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS)
      .success(() ->
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Closes a case
    #----------------------------------------------------------------------------
    closeCase: (caseObj, note, callback) ->
      params = {note: note}

      $http.post('/case/close/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS)
      .success(() ->
        caseObj.is_closed = true
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Re-opens a case
    #----------------------------------------------------------------------------
    reopenCase: (caseObj, note, callback) ->
      params = {note: note}

      $http.post('/case/reopen/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS)
      .success(() ->
        caseObj.is_closed = false
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Re-labels a case
    #----------------------------------------------------------------------------
    relabelCase: (caseObj, labels, callback) ->
      params = {
        labels: (l.id for l in labels)
      }

      $http.post('/case/label/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS)
      .success(() ->
        caseObj.labels = labels
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Updates a case's summary
    #----------------------------------------------------------------------------
    updateCaseSummary: (caseObj, summary, callback) ->
      params = {summary: summary}

      $http.post('/case/update_summary/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS)
      .success(() ->
        caseObj.summary = summary
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Reply in a case
    #----------------------------------------------------------------------------
    replyToCase: (caseObj, text, callback) ->
      params = {text: text}

      $http.post('/case/reply/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS)
      .success(() ->
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Navigates to the read page for the given case
    #----------------------------------------------------------------------------
    navigateToCase: (caseObj, withAlert) ->
      caseUrl = '/case/read/' + caseObj.id + '/'
      if withAlert
        caseUrl += '?alert=' + withAlert
      $window.location.href = caseUrl

    #----------------------------------------------------------------------------
    # Fetches timeline events
    #----------------------------------------------------------------------------
    fetchTimeline: (caseObj, after, callback) ->
      params = {after: after}

      $http.get('/case/timeline/' + caseObj.id + '/?' + $.param(params))
      .success((data) =>
        @_processTimeline(data.results)
        callback(data.results, data.max_time)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Convert search object to URL params
    #----------------------------------------------------------------------------
    _searchToParams: (search) ->
      params = {}
      params.folder = search.folder
      params.assignee = if search.assignee then search.assignee.id else null
      params.label = if search.label then search.label.id else null
      return params

    #----------------------------------------------------------------------------
    # Processes incoming cases
    #----------------------------------------------------------------------------
    _processCases: (cases) ->
      for c in cases
        c.opened_on = parseIso8601(c.opened_on)

    #----------------------------------------------------------------------------
    # Processes incoming case timeline items
    #----------------------------------------------------------------------------
    _processTimeline: (events) ->
      for event in events
        # parse datetime string
        event.time = parseIso8601(event.time)
        event.is_action = event.type == 'A'
        event.is_message_in = event.type == 'M' and event.item.direction == 'I'
        event.is_message_out = event.type == 'M' and event.item.direction == 'O'
]


#=====================================================================
# Partner service
#=====================================================================
services.factory 'PartnerService', ['$http', ($http) ->
  new class PartnerService

    fetchUsers: (partner, callback) ->
      $http.get('/partner/users/' + partner.id + '/')
      .success((data) =>
        callback(data.users)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Delete the given partner
    #----------------------------------------------------------------------------
    deletePartner: (partner, callback) ->
      $http.post('/partner/delete/' + partner.id + '/', {}, DEFAULT_POST_OPTS)
      .success(() ->
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)
]


#=====================================================================
# User service
#=====================================================================
services.factory 'UserService', ['$http', ($http) ->
  new class UserService

    #----------------------------------------------------------------------------
    # Delete the given user
    #----------------------------------------------------------------------------
    deleteUser: (userId, callback) ->
      $http.post('/user/delete/' + userId + '/', {}, DEFAULT_POST_OPTS)
      .success(() ->
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)
]


#=====================================================================
# Utils service
#=====================================================================
services.factory 'UtilsService', ['$window', '$uibModal', ($window, $uibModal) ->
  new class UtilsService

    displayAlert: (type, message) ->
      # TODO angularize ?
      $window.displayAlert(type, message)

    navigate: (url) ->
      $window.location.href = url

    navigateBack: () ->
      $window.history.back();

    refresh: () ->
      @navigate($window.location.href)

    confirmModal: (prompt, style, callback) ->
      resolve = {prompt: (() -> prompt), style: (() -> style)}
      $uibModal.open({templateUrl: 'confirmModal.html', controller: 'ConfirmModalController', resolve: resolve})
      .result.then () ->
        callback()

    editModal: (title, initial, maxLength, callback) ->
      resolve = {title: (() -> title), initial: (() -> initial), maxLength: (() -> maxLength)}
      $uibModal.open({templateUrl: 'editModal.html', controller: 'EditModalController', resolve: resolve})
      .result.then (text) ->
        callback(text)

    assignModal: (title, prompt, partners, callback) ->
      resolve = {title: (() -> title), prompt: (() -> prompt), partners: (() -> partners)}
      $uibModal.open({templateUrl: 'assignModal.html', controller: 'AssignModalController', resolve: resolve})
      .result.then (assignee) ->
        callback(assignee)

    noteModal: (title, prompt, style, maxLength, callback) ->
      resolve = {title: (() -> title), prompt: (() -> prompt), style: (() -> style), maxLength: (() -> maxLength)}
      $uibModal.open({templateUrl: 'noteModal.html', controller: 'NoteModalController', resolve: resolve})
      .result.then (note) ->
        callback(note)

    labelModal: (title, prompt, labels, initial, callback) ->
      resolve = {title: (() -> title), prompt: (() -> prompt), labels: (() -> labels), initial: (() -> initial)}
      $uibModal.open({templateUrl: 'labelModal.html', controller: 'LabelModalController', resolve: resolve})
      .result.then (selectedLabels) ->
        callback(selectedLabels)
]
