services = angular.module('upartners.services', []);


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
    fetchOldMessages: (label, search, page, callback) ->
      searchParams = if search then @_searchToParams(search) else ''
      otherParams = {start_time: formatIso8601(@start_time), page: page, label: if label then label.id else null}

      $http.get('/message/?' + $.param(otherParams) + '&' + searchParams)
      .success (data) =>
        @_processMessages(data.results)
        callback(data.results, data.total, data.has_more)

    #----------------------------------------------------------------------------
    # Fetches new messages for the given label
    #----------------------------------------------------------------------------
    fetchNewMessages: (label, search, afterTime, afterId, callback) ->
      searchParams = @_searchToParams(search)
      otherParams = {after_time: formatIso8601(afterTime), after_id: afterId, label: if label then label.id else null}

      $http.get('/message/?' + $.param(otherParams) + '&' + searchParams)
      .success (data) =>
        @_processMessages(data.results)
        callback(data.results, data.total, data.max_time, data.max_id)

    #----------------------------------------------------------------------------
    # Starts a message export
    #----------------------------------------------------------------------------
    startExport: (label, search, callback) ->
      searchParams = @_searchToParams(search)
      otherParams = {label: if label then label.id else null}

      $http.post('/messageexport/create/?' + $.param(otherParams) + '&' + searchParams)
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

      @_messagesSend(urns, contacts, text, callback)

    #----------------------------------------------------------------------------
    # Flag or un-flag messages
    #----------------------------------------------------------------------------
    flagMessages: (messages, flagged) ->
      action = if flagged then 'flag' else 'unflag'
      @_messagesAction(messages, action, null, () ->
        for msg in messages
          msg.flagged = flagged
      )

    #----------------------------------------------------------------------------
    # Label messages
    #----------------------------------------------------------------------------
    labelMessages: (messages, label) ->
      without_label = []
      for msg in messages
        if label.name not in msg.labels
          without_label.push(msg)
          msg.labels.push(label.name)

      if without_label.length > 0
        @_messagesAction(without_label, 'label', label.name)

    #----------------------------------------------------------------------------
    # Archive messages
    #----------------------------------------------------------------------------
    archiveMessages: (messages) ->
      @_messagesAction(messages, 'archive', null, () ->
        for msg in messages
          msg.archived = true
      )

    #----------------------------------------------------------------------------
    # Send new message
    #----------------------------------------------------------------------------
    sendNewMessage: (urn_or_contact, text, callback) ->
      if urn_or_contact.hasOwnProperty('uuid')
        @_messagesSend([], [urn_or_contact.uuid], text, callback)
      else
        @_messagesSend([urn_or_contact.urn], [], text, callback)


    #----------------------------------------------------------------------------
    # Convert search object to URL params
    #----------------------------------------------------------------------------
    _searchToParams: (search) ->
      params = {}
      params.text = search.text
      params.after = formatIso8601(search.after)
      params.before = formatIso8601(search.before)
      params.groups = (g.uuid for g in search.groups).join(',')
      params.reverse = search.reverse
      $.param(params)

    #----------------------------------------------------------------------------
    # POSTs to the messages action endpoint
    #----------------------------------------------------------------------------
    _messagesAction: (messages, action, label, callback) ->
      data = new FormData();
      data.append('message_ids', (msg.id for msg in messages))
      data.append('label', label)

      $http.post '/message/action/' + action + '/', data, DEFAULT_POST_OPTS
      .success () =>
        if callback
          callback()

    #----------------------------------------------------------------------------
    # POSTs to the messages send endpoint and returns new broadcast id
    #----------------------------------------------------------------------------
    _messagesSend: (urns, contacts, text, callback) ->
      data = new FormData();
      data.append('urns', urns)
      data.append('contacts', contacts)
      data.append('text', text)
      $http.post('/message/send/', data, DEFAULT_POST_OPTS)
      .success (data) =>
        callback(data.broadcast_id)

    #----------------------------------------------------------------------------
    # Processes incoming messages
    #----------------------------------------------------------------------------
    _processMessages: (messages) ->
      for msg in messages
        # parse datetime string
        msg.time = parseIso8601(msg.time)
        msg.archived = false
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
    fetchOldCases: (label, status, startTime, page, callback) ->
      params = {}
      params['label'] = (if label then label.id else null)
      params['status'] = status
      params['before_time'] = formatIso8601(startTime)
      params['page'] = page

      $http.get('/case/search/?' + $.param(params))
      .success (data) =>
        @_processCases(data.results)
        callback(data.results, data.total, data.has_more)

    #----------------------------------------------------------------------------
    # Fetches new cases
    #----------------------------------------------------------------------------
    fetchNewCases: (label, status, startTime, afterId, callback) ->
      params = {}
      params['label'] = (if label then label.id else null)
      params['status'] = status
      if afterId
        params['after_id'] = afterId
      else
        params['after_time'] = formatIso8601(startTime)

      $http.get('/case/search/?' + $.param(params))
      .success (data) =>
        @_processCases(data.results)
        callback(data.results, data.max_id)

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
    openCase: (message, assignee, callback) ->
      data = new FormData()
      data.append('assignee_id', if assignee then assignee.id else null)
      data.append('message_id', message.id)
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
        callback()

    #----------------------------------------------------------------------------
    # Re-assigns a case
    #----------------------------------------------------------------------------
    reassignCase: (_case, assignee, callback) ->
      data = new FormData()
      data.append('assignee_id', assignee.id)

      $http.post('/case/reassign/' + _case.id + '/', data, DEFAULT_POST_OPTS)
      .success () ->
        callback()

    #----------------------------------------------------------------------------
    # Closes a case
    #----------------------------------------------------------------------------
    closeCase: (_case, note, callback) ->
      data = new FormData()
      data.append('note', note)

      $http.post('/case/close/' + _case.id + '/', data, DEFAULT_POST_OPTS)
      .success () ->
        _case.is_closed = true
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
        callback()

    #----------------------------------------------------------------------------
    # Labels a case
    #----------------------------------------------------------------------------
    labelCase: (_case, labels, callback) ->
      data = new FormData()
      data.append('labels', (l.id for l in labels))

      $http.post('/case/label/' + _case.id + '/', data, DEFAULT_POST_OPTS)
      .success () ->
        _case.labels = labels
        callback()

    #----------------------------------------------------------------------------
    # Fetches timeline events
    #----------------------------------------------------------------------------
    fetchTimeline: (_case, lastEventTime, lastMessageId, lastActionId, callback) ->
      params = {
        since_event_time: (formatIso8601 lastEventTime),
        since_message_id: lastMessageId,
        since_action_id: lastActionId
      }

      $http.get('/case/timeline/' + _case.id + '/?' + $.param(params))
      .success (data) =>
        @_processEvents(data.results)

        newLastEventTime = parseIso8601(data.last_event_time) or lastEventTime
        newLastMessageId = data.last_message_id or lastMessageId
        newLastActionId = data.last_action_id or lastActionId

        callback(data.results, newLastEventTime, newLastMessageId, newLastActionId)

    #----------------------------------------------------------------------------
    # Processes incoming cases
    #----------------------------------------------------------------------------
    _processCases: (cases) ->
      for c in cases
        c.opened_on = parseIso8601(c.opened_on)

    #----------------------------------------------------------------------------
    # Processes incoming case events
    #----------------------------------------------------------------------------
    _processEvents: (events) ->
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