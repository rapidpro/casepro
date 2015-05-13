#============================================================================
# Application services
#============================================================================

services = angular.module('cases.services', ['cases.modals']);


DEFAULT_POST_OPTS = {transformRequest: angular.identity, headers: {'Content-Type': undefined}}

#=====================================================================
# Date utilities
#=====================================================================

parseIso8601 = (str) ->
  if str then new Date(Date.parse str) else null

formatIso8601 = (date) ->
  if date then date.toISOString() else null


#=====================================================================
# Message service
#=====================================================================

services.factory 'MessageService', ['$rootScope', '$http', ($rootScope, $http) ->
  new class MessageService

    #----------------------------------------------------------------------------
    # Fetches old messages for the given label
    #----------------------------------------------------------------------------
    fetchOld: (search, before, page, callback) ->
      params = @_searchToParams(search)
      params.before = formatIso8601(before)
      params.page = page

      $http.get('/message/?' + $.param(params))
      .success (data) =>
        @_processMessages(data.results)
        callback(data.results, data.total, data.has_more)

    #----------------------------------------------------------------------------
    # Fetches new messages for the given label
    #----------------------------------------------------------------------------
    fetchNew: (search, after, before, callback) ->
      params = @_searchToParams(search)
      params.after = formatIso8601(after)
      params.before = formatIso8601(before)

      $http.get('/message/?' + $.param(params))
      .success (data) =>
        @_processMessages(data.results)

        if data.results.length > 0
          maxTime = data.results[0].time
          maxId = data.results[0].id
        else
          maxTime = null
          maxId = null

        callback(data.results, maxTime, maxId)

    #----------------------------------------------------------------------------
    # Fetches history for a single message
    #----------------------------------------------------------------------------
    fetchHistory: (message, callback) ->
      $http.get('/message/history/' + message.id + '/')
      .success (data) =>
        @_processMessageActions(data.actions)
        callback(data.actions)

    #----------------------------------------------------------------------------
    # Starts a message export
    #----------------------------------------------------------------------------
    startExport: (search, callback) ->
      params = @_searchToParams(search)
      $http.post('/messageexport/create/?' + $.param(params))
      .success () =>
        callback()

    #----------------------------------------------------------------------------
    # Reply-to messages
    #----------------------------------------------------------------------------
    replyToMessages: (messages, text, callback) ->
      # it's generally better to send via URNs but anon orgs won't have them
      urns = []
      contacts = []
      for msg in messages
        if msg.urn
          urns.push(msg.urn)
        else
          contacts.push(msg.contact)

      @_messagesSend('B', text, urns, contacts, null, callback)

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
      data = new FormData()
      data.append('labels', (l.id for l in labels))

      $http.post('/message/label/' + message.id + '/', data, DEFAULT_POST_OPTS)
      .success () ->
        message.labels = labels
        if callback
          callback()

    #----------------------------------------------------------------------------
    # Reply to a contact in a case
    #----------------------------------------------------------------------------
    replyInCase: (text, _case, callback) ->
      @_messagesSend('C', text, [], [_case.contact.uuid], _case, callback)

    #----------------------------------------------------------------------------
    # Forward a message to a URN
    #----------------------------------------------------------------------------
    forwardToUrn: (text, urn, callback) ->
        @_messagesSend('F', text, [urn.urn], [], null, callback)

    #----------------------------------------------------------------------------
    # Convert search object to URL params
    #----------------------------------------------------------------------------
    _searchToParams: (search) ->
      params = {}
      params.view = search.view
      params.text = search.text
      params.after = formatIso8601(search.after)
      params.before = formatIso8601(search.before)
      params.groups = (g.uuid for g in search.groups).join(',')
      params.contact = search.contact
      params.label = if search.label then search.label.id else null
      return params

    #----------------------------------------------------------------------------
    # POSTs to the messages action endpoint
    #----------------------------------------------------------------------------
    _messagesAction: (messages, action, label, callback) ->
      data = new FormData();
      data.append('messages', (m.id for m in messages))
      if label
        data.append('label', label.id)

      $http.post '/message/action/' + action + '/', data, DEFAULT_POST_OPTS
      .success () =>
        if callback
          callback()

    #----------------------------------------------------------------------------
    # POSTs to the messages send endpoint and returns new broadcast id
    #----------------------------------------------------------------------------
    _messagesSend: (activity, text, urns, contacts, _case, callback) ->
      data = new FormData();
      data.append('activity', activity)
      data.append('text', text)
      data.append('urns', urns)
      data.append('contacts', contacts)
      if _case
        data.append('case', _case.id)
      $http.post('/message/send/', data, DEFAULT_POST_OPTS)
      .success (data) =>
        callback()

    #----------------------------------------------------------------------------
    # Processes incoming messages
    #----------------------------------------------------------------------------
    _processMessages: (messages) ->
      for msg in messages
        # parse datetime string
        msg.time = parseIso8601(msg.time)

    #----------------------------------------------------------------------------
    # Processes incoming message actions
    #----------------------------------------------------------------------------
    _processMessageActions: (actions) ->
      for action in actions
        action.created_on = parseIso8601(action.created_on)
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
      .success () ->
        callback()
]


#=====================================================================
# Case service
#=====================================================================

services.factory 'CaseService', ['$http', ($http) ->
  new class CaseService

    #----------------------------------------------------------------------------
    # Fetches old cases
    #----------------------------------------------------------------------------
    fetchOld: (search, before, page, callback) ->
      params = @_searchToParams(search)
      params.before = formatIso8601(before)
      params.page = page

      $http.get('/case/search/?' + $.param(params))
      .success (data) =>
        @_processCases(data.results)
        callback(data.results, data.total, data.has_more)

    #----------------------------------------------------------------------------
    # Fetches new cases
    #----------------------------------------------------------------------------
    fetchNew: (search, after, before, callback) ->
      params = @_searchToParams(search)
      params.after = formatIso8601(after)
      params.before = formatIso8601(before)

      $http.get('/case/search/?' + $.param(params))
      .success (data) =>
        @_processCases(data.results)
        callback(data.results)

    #----------------------------------------------------------------------------
    # Fetches an existing case by it's id
    #----------------------------------------------------------------------------
    fetchCase: (caseId, callback) ->
      $http.get('/case/fetch/' + caseId + '/')
      .success (_case) =>
        @_processCases([_case])
        callback(_case)

    #----------------------------------------------------------------------------
    # Opens a new case
    #----------------------------------------------------------------------------
    openCase: (message, summary, assignee, callback) ->
      data = new FormData()
      data.append('message', message.id)
      data.append('summary', summary)
      if assignee
        data.append('assignee', assignee.id)

      $http.post('/case/open/', data, DEFAULT_POST_OPTS)
      .success (_case) ->
        callback(_case)

    #----------------------------------------------------------------------------
    # Adds a note to a case
    #----------------------------------------------------------------------------
    noteCase: (_case, note, callback) ->
      data = new FormData()
      data.append('note', note)

      $http.post('/case/note/' + _case.id + '/', data, DEFAULT_POST_OPTS)
      .success () ->
        if callback
          callback()

    #----------------------------------------------------------------------------
    # Re-assigns a case
    #----------------------------------------------------------------------------
    reassignCase: (_case, assignee, callback) ->
      data = new FormData()
      data.append('assignee_id', assignee.id)

      $http.post('/case/reassign/' + _case.id + '/', data, DEFAULT_POST_OPTS)
      .success () ->
        if callback
          callback()

    #----------------------------------------------------------------------------
    # Closes cases
    #----------------------------------------------------------------------------
    closeCases: (cases, note, callback) ->
      data = new FormData()
      data.append('cases', (c.id for c in cases))
      data.append('note', note)

      $http.post('/case/close/', data, DEFAULT_POST_OPTS)
      .success () ->
        for c in cases
          c.is_closed = true
        if callback
          callback()

    #----------------------------------------------------------------------------
    # Re-opens a case
    #----------------------------------------------------------------------------
    reopenCase: (_case, note, callback) ->
      data = new FormData()
      data.append('note', note)

      $http.post('/case/reopen/' + _case.id + '/', data, DEFAULT_POST_OPTS)
      .success () ->
        _case.is_closed = false
        if callback
          callback()

    #----------------------------------------------------------------------------
    # Re-labels a case
    #----------------------------------------------------------------------------
    relabelCase: (_case, labels, callback) ->
      data = new FormData()
      data.append('labels', (l.id for l in labels))

      $http.post('/case/label/' + _case.id + '/', data, DEFAULT_POST_OPTS)
      .success () ->
        _case.labels = labels
        if callback
          callback()

    #----------------------------------------------------------------------------
    # Updates a case's summary
    #----------------------------------------------------------------------------
    updateCaseSummary: (_case, summary, callback) ->
      data = new FormData()
      data.append('summary', summary)

      $http.post('/case/update_summary/' + _case.id + '/', data, DEFAULT_POST_OPTS)
      .success () ->
        _case.summary = summary
        if callback
          callback()

    #----------------------------------------------------------------------------
    # Fetches timeline events
    #----------------------------------------------------------------------------
    fetchTimeline: (_case, after, before, callback) ->
      params = {
        after: formatIso8601(after),
        before: formatIso8601(before),
      }

      $http.get('/case/timeline/' + _case.id + '/?' + $.param(params))
      .success (data) =>
        @_processTimeline(data.results)
        callback(data.results)

    #----------------------------------------------------------------------------
    # Convert search object to URL params
    #----------------------------------------------------------------------------
    _searchToParams: (search) ->
      params = {}
      params.view = search.view
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
# Utils service
#=====================================================================

services.factory 'UtilsService', ['$window', '$modal', ($window, $modal) ->
  new class UtilsService

    displayAlert: (type, message) ->
      # TODO angularize ?
      $window.displayAlert(type, message)

    navigate: (url) ->
      $window.location.href = url

    refresh: () ->
      @navigate($window.location.href)

    confirmModal: (prompt, style, callback) ->
      resolve = {prompt: (() -> prompt), style: (() -> style)}
      $modal.open({templateUrl: 'confirmModal.html', controller: 'ConfirmModalController', resolve: resolve})
      .result.then () ->
        callback()

    editModal: (title, initial, callback) ->
      resolve = {title: (() -> title), initial: (() -> initial)}
      $modal.open({templateUrl: 'editModal.html', controller: 'EditModalController', resolve: resolve})
      .result.then (text) ->
        callback(text)

    assignModal: (title, prompt, partners, callback) ->
      resolve = {title: (() -> title), prompt: (() -> prompt), partners: (() -> partners)}
      $modal.open({templateUrl: 'assignModal.html', controller: 'AssignModalController', resolve: resolve})
      .result.then (assignee) ->
        callback(assignee)

    noteModal: (title, prompt, style, callback) ->
      resolve = {title: (() -> title), prompt: (() -> prompt), style: (() -> style)}
      $modal.open({templateUrl: 'noteModal.html', controller: 'NoteModalController', resolve: resolve})
      .result.then (note) ->
        callback(note)

    labelModal: (title, prompt, labels, initial, callback) ->
      resolve = {title: (() -> title), prompt: (() -> prompt), labels: (() -> labels), initial: (() -> initial)}
      $modal.open({templateUrl: 'labelModal.html', controller: 'LabelModalController', resolve: resolve})
      .result.then (selectedLabels) ->
        callback(selectedLabels)
]