#============================================================================
# Application services
#============================================================================

services = angular.module('cases.services', ['cases.modals']);


DEFAULT_POST_OPTS = {transformRequest: angular.identity, headers: {'Content-Type': undefined}}
POST_DEFAULTS = {headers : {'Content-Type': 'application/x-www-form-urlencoded'}}

DEFAULT_ERR_HANDLER = (data, status, headers, config) =>
  console.error("Request error (status = " + status + ")")

#=====================================================================
# Incoming message service
#=====================================================================

services.factory 'MessageService', ['$rootScope', '$http', '$httpParamSerializer', ($rootScope, $http, $httpParamSerializer) ->
  new class MessageService

    #----------------------------------------------------------------------------
    # Fetches old messages for the given search
    #----------------------------------------------------------------------------
    fetchOld: (search, before, page, callback) ->
      params = @_searchToParams(search)
      if !search.before
        params.before = utils.formatIso8601(before)
      params.page = page

      $http.get('/message/search/?' + $httpParamSerializer(params))
      .success((data) =>
        utils.parseDates(data.results, 'time')

        callback(data.results, data.has_more)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Fetches new messages for the given search
    #----------------------------------------------------------------------------
    fetchNew: (search, after, before, callback) ->
      params = @_searchToParams(search)
      params.after = utils.formatIso8601(after)
      params.before = utils.formatIso8601(before)

      $http.get('/message/?' + $httpParamSerializer(params))
      .success((data) =>
        utils.parseDates(data.results, 'time')

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
    fetchHistory: (message) ->
      return $http.get('/message/history/' + message.id + '/').then((response) ->
        return utils.parseDates(response.data.actions, 'created_on')
      )

    #----------------------------------------------------------------------------
    # Starts a message export
    #----------------------------------------------------------------------------
    startExport: (search) ->
      return $http.post('/messageexport/create/?' + $httpParamSerializer(@_searchToParams(search)))

    #----------------------------------------------------------------------------
    # Reply-to messages
    #----------------------------------------------------------------------------
    replyToMessages: (messages, text, callback) ->
      params = {
        text: text,
        messages: (m.id for m in messages)
      }

      $http.post('/message/bulk_reply/', utils.toFormData(params), DEFAULT_POST_OPTS)
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
      data = utils.toFormData({
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

      $http.post('/message/forward/' + message.id + '/', utils.toFormData(params), DEFAULT_POST_OPTS)
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
        after: utils.formatIso8601(search.after),
        before: utils.formatIso8601(search.before),
        groups: if search.groups then (g.uuid for g in search.groups).join(',') else null,
        contact: if search.contact then search.contact.id else null,
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

      $http.post('/message/action/' + action + '/', utils.toFormData(params), DEFAULT_POST_OPTS)
      .success(() =>
        if callback
          callback()
      ).error(DEFAULT_ERR_HANDLER)
]


#=====================================================================
# Incoming message service
#=====================================================================

services.factory 'OutgoingService', ['$rootScope', '$http', '$httpParamSerializer', ($rootScope, $http, $httpParamSerializer) ->
  new class OutgoingService

    #----------------------------------------------------------------------------
    # Fetches old outgoing messages for the given search
    #----------------------------------------------------------------------------
    fetchOld: (search, startTime, page, callback) ->
      params = @_outboxSearchToParams(search, startTime, page)

      $http.get('/outgoing/search/?' + $httpParamSerializer(params))
      .success((data) =>
        utils.parseDates(data.results, 'time')
        callback(data.results, data.has_more)
      ).error(DEFAULT_ERR_HANDLER)

    fetchReplies: (search, startTime, page, callback) ->
      params = @_replySearchToParams(search, startTime, page)

      $http.get('/outgoing/search_replies/?' + $httpParamSerializer(params))
      .success((data) =>
        utils.parseDates(data.results, 'time')
        callback(data.results, data.has_more)
      ).error(DEFAULT_ERR_HANDLER)

    startReplyExport: (search) ->
      return $http.post('/replyexport/create/?' + $httpParamSerializer(@_replySearchToParams(search, null, null)))

    #----------------------------------------------------------------------------
    # Convert a regular outbox search object to URL params
    #----------------------------------------------------------------------------
    _outboxSearchToParams: (search, startTime, page) ->
      return {
        folder: search.folder,
        text: search.text,
        contact: if search.contact then search.contact.id else null,
        before: utils.formatIso8601(startTime),
        page: page
      }

    #----------------------------------------------------------------------------
    # Convert a reply search object to URL params
    #----------------------------------------------------------------------------
    _replySearchToParams: (search, startTime, page) ->
      return {
        partner: search.partner.id,
        after: utils.formatIso8601(search.after),
        before: if search.before then utils.formatIso8601(search.before) else utils.formatIso8601(startTime),
        page: page
      }
]


#=====================================================================
# Case service
#=====================================================================

services.factory 'CaseService', ['$http', '$httpParamSerializer', '$window', ($http, $httpParamSerializer, $window) ->
  new class CaseService

    #----------------------------------------------------------------------------
    # Fetches old cases
    #----------------------------------------------------------------------------
    fetchOld: (search, before, page, callback) ->
      params = @_searchToParams(search)
      params.before = utils.formatIso8601(before)
      params.page = page

      $http.get('/case/search/?' + $httpParamSerializer(params))
      .success((data) =>
        utils.parseDates(data.results, 'opened_on')
        callback(data.results, data.has_more)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Fetches new cases
    #----------------------------------------------------------------------------
    fetchNew: (search, after, before, callback) ->
      params = @_searchToParams(search)
      params.after = utils.formatIso8601(after)
      params.before = utils.formatIso8601(before)

      $http.get('/case/search/?' + $httpParamSerializer(params))
      .success((data) =>
        utils.parseDates(data.results, 'opened_on')
        callback(data.results)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Fetches an existing case by it's id
    #----------------------------------------------------------------------------
    fetchCase: (caseId, callback) ->
      $http.get('/case/fetch/' + caseId + '/')
      .success((caseObj) =>
        utils.parseDates([caseObj], 'opened_on')
        callback(caseObj)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Starts a case export
    #----------------------------------------------------------------------------
    startExport: (search) ->
      return $http.post('/caseexport/create/?' + $httpParamSerializer(@_searchToParams(search)))

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

      $http.post('/case/open/', utils.toFormData(params), DEFAULT_POST_OPTS)
      .success((data) ->
        callback(data['case'], data['is_new'])
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Adds a note to a case
    #----------------------------------------------------------------------------
    addNote: (caseObj, note) ->
      return $http.post('/case/note/' + caseObj.id + '/', $httpParamSerializer({note: note}), POST_DEFAULTS)

    #----------------------------------------------------------------------------
    # Re-assigns a case
    #----------------------------------------------------------------------------
    reassign: (caseObj, assignee) ->
      params = {assignee: assignee.id}

      return $http.post('/case/reassign/' + caseObj.id + '/', $httpParamSerializer(params), POST_DEFAULTS)
      .then(() ->
        caseObj.assignee = assignee
      )

    #----------------------------------------------------------------------------
    # Closes a case
    #----------------------------------------------------------------------------
    close: (caseObj, note) ->
      return $http.post('/case/close/' + caseObj.id + '/', $httpParamSerializer({note: note}), POST_DEFAULTS)
      .then(() ->
        caseObj.is_closed = true
      )

    #----------------------------------------------------------------------------
    # Re-opens a case
    #----------------------------------------------------------------------------
    reopen: (caseObj, note) ->
      return $http.post('/case/reopen/' + caseObj.id + '/', $httpParamSerializer({note: note}), POST_DEFAULTS)
      .then(() ->
        caseObj.is_closed = false
      )

    #----------------------------------------------------------------------------
    # Re-labels a case
    #----------------------------------------------------------------------------
    relabelCase: (caseObj, labels, callback) ->
      params = {
        labels: (l.id for l in labels)
      }

      $http.post('/case/label/' + caseObj.id + '/', utils.toFormData(params), DEFAULT_POST_OPTS)
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

      $http.post('/case/update_summary/' + caseObj.id + '/', utils.toFormData(params), DEFAULT_POST_OPTS)
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

      $http.post('/case/reply/' + caseObj.id + '/', utils.toFormData(params), DEFAULT_POST_OPTS)
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

      $http.get('/case/timeline/' + caseObj.id + '/?' + $httpParamSerializer(params))
      .success((data) =>
        @_processTimeline(data.results)
        callback(data.results, data.max_time)
      ).error(DEFAULT_ERR_HANDLER)

    #----------------------------------------------------------------------------
    # Convert search object to URL params
    #----------------------------------------------------------------------------
    _searchToParams: (search) ->
      return {
        folder: search.folder,
        assignee: if search.assignee then search.assignee.id else null,
        label: if search.label then search.label.id else null
      }

    #----------------------------------------------------------------------------
    # Processes incoming case timeline items
    #----------------------------------------------------------------------------
    _processTimeline: (events) ->
      for event in events
        # parse datetime string
        event.time = utils.parseIso8601(event.time)
        event.is_action = event.type == 'A'
        event.is_message_in = event.type == 'M' and event.item.direction == 'I'
        event.is_message_out = event.type == 'M' and event.item.direction == 'O'
]


#=====================================================================
# Label service
#=====================================================================

services.factory 'LabelService', ['$http', ($http) ->
  new class LabelService

    #----------------------------------------------------------------------------
    # Deletes a label
    #----------------------------------------------------------------------------
    delete: (label) ->
      return $http.post('/label/delete/' + label.id + '/')
]


#=====================================================================
# Partner service
#=====================================================================
services.factory 'PartnerService', ['$http', ($http) ->
  new class PartnerService

    #----------------------------------------------------------------------------
    # Fetches users with activity statistics for the given partner
    #----------------------------------------------------------------------------
    fetchUsers: (partner) ->
      return $http.get('/partner/users/' + partner.id + '/').then((response) -> response.data.results)

    #----------------------------------------------------------------------------
    # Delete the given partner
    #----------------------------------------------------------------------------
    delete: (partner) ->
      return $http.post('/partner/delete/' + partner.id + '/')
]


#=====================================================================
# User service
#=====================================================================
services.factory 'UserService', ['$http', ($http) ->
  new class UserService

    #----------------------------------------------------------------------------
    # Delete the given user
    #----------------------------------------------------------------------------
    delete: (user) ->
      return $http.post('/user/delete/' + user.id + '/')
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
