#============================================================================
# Application services
#============================================================================

services = angular.module('cases.services', ['cases.modals']);

POST_DEFAULTS = {headers : {'Content-Type': 'application/x-www-form-urlencoded'}}

# TODO switch POSTs to use url-encoded data ($httpParamSerializer/POST_DEFAULTS) and remove usage of toFormData/DEFAULT_POST_OPTS
toFormData = (params) ->
    data = new FormData()
    for own key, val of params
      if angular.isArray(val)
        val = (item.toString() for item in val).join(',')
      else if val
        val = val.toString()  # required for https://bugzilla.mozilla.org/show_bug.cgi?id=819328

      if val
        data.append(key, val)

    return data

DEFAULT_POST_OPTS = {transformRequest: angular.identity, headers: {'Content-Type': undefined}}

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
    fetchOld: (search, before, page) ->
      params = @_searchToParams(search)
      if !search.before
        params.before = utils.formatIso8601(before)
      params.page = page

      return $http.get('/message/search/?' + $httpParamSerializer(params)).then((response) ->
        utils.parseDates(response.data.results, 'time')
        return {results: response.data.results, hasMore: response.data.has_more}
      )

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
    bulkReply: (messages, text) ->
      params = {
        text: text,
        messages: (m.id for m in messages)
      }

      return $http.post('/message/bulk_reply/', toFormData(params), DEFAULT_POST_OPTS)

    #----------------------------------------------------------------------------
    # Flag or un-flag messages
    #----------------------------------------------------------------------------
    bulkFlag: (messages, flagged) ->
      action = if flagged then 'flag' else 'unflag'

      return @_bulkAction(messages, action, null).then(() ->
        for msg in messages
          msg.flagged = flagged
      )

    #----------------------------------------------------------------------------
    # Label messages with the given label
    #----------------------------------------------------------------------------
    bulkLabel: (messages, label) ->
      without_label = []
      for msg in messages
        if label not in msg.labels
          without_label.push(msg)
          msg.labels.push(label)

      return @_bulkAction(without_label, 'label', label)

    #----------------------------------------------------------------------------
    # Archive messages
    #----------------------------------------------------------------------------
    bulkArchive: (messages) ->
      return @_bulkAction(messages, 'archive', null).then(() ->
        for msg in messages
          msg.archived = true
      )

    #----------------------------------------------------------------------------
    # Restore (i.e. un-archive) messages
    #----------------------------------------------------------------------------
    bulkRestore: (messages) ->
      return @_bulkAction(messages, 'restore', null).then(() ->
        for msg in messages
          msg.archived = false
      )

    #----------------------------------------------------------------------------
    # Relabel the given message (removing labels if necessary)
    #----------------------------------------------------------------------------
    relabel: (message, labels) ->
      data = toFormData({
        labels: (l.id for l in labels)
      })

      return $http.post('/message/label/' + message.id + '/', data, DEFAULT_POST_OPTS).then(() ->
        message.labels = labels
      )

    #----------------------------------------------------------------------------
    # Forward a message to a URN
    #----------------------------------------------------------------------------
    forward: (message, text, urn) ->
      params = {
        text: text,
        urns: [urn.urn]
      }

      return $http.post('/message/forward/' + message.id + '/', toFormData(params), DEFAULT_POST_OPTS)

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
    # POSTs to the messages bulk action endpoint
    #----------------------------------------------------------------------------
    _bulkAction: (messages, action, label) ->
      params = {
        messages: (m.id for m in messages)
      }
      if label
        params.label = label.id

      return $http.post('/message/action/' + action + '/', toFormData(params), DEFAULT_POST_OPTS)
]


#=====================================================================
# Incoming message service
#=====================================================================

services.factory 'OutgoingService', ['$rootScope', '$http', '$httpParamSerializer', ($rootScope, $http, $httpParamSerializer) ->
  new class OutgoingService

    #----------------------------------------------------------------------------
    # Fetches old outgoing messages for the given search
    #----------------------------------------------------------------------------
    fetchOld: (search, startTime, page) ->
      params = @_outboxSearchToParams(search, startTime, page)

      return $http.get('/outgoing/search/?' + $httpParamSerializer(params)).then((response) ->
        utils.parseDates(response.data.results, 'time')
        return {results: response.data.results, hasMore: response.data.has_more}
      )

    fetchReplies: (search, startTime, page) ->
      params = @_replySearchToParams(search, startTime, page)

      return $http.get('/outgoing/search_replies/?' + $httpParamSerializer(params)).then((response) ->
        utils.parseDates(response.data.results, 'time')
        return {results: response.data.results, hasMore: response.data.has_more}
      )

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
    fetchOld: (search, before, page) ->
      params = @_searchToParams(search)
      params.before = utils.formatIso8601(before)
      params.page = page

      return $http.get('/case/search/?' + $httpParamSerializer(params)).then((response) ->
        utils.parseDates(response.data.results, 'opened_on')
        return {results: response.data.results, hasMore: response.data.has_more}
      )

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
    open: (message, summary, assignee) ->
      params = {
        message: message.id,
        summary: summary
      }
      if assignee
        params.assignee = assignee.id

      return $http.post('/case/open/', toFormData(params), DEFAULT_POST_OPTS).then((response) ->
        caseObj = response.data['case']
        caseObj.isNew = response.data['is_new']
        return caseObj
      )

    #----------------------------------------------------------------------------
    # Adds a note to a case
    #----------------------------------------------------------------------------
    addNote: (caseObj, note) ->
      return $http.post('/case/note/' + caseObj.id + '/', toFormData({note: note}), DEFAULT_POST_OPTS)

    #----------------------------------------------------------------------------
    # Re-assigns a case
    #----------------------------------------------------------------------------
    reassign: (caseObj, assignee) ->
      params = {assignee: assignee.id}

      return $http.post('/case/reassign/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS)
      .then(() ->
        caseObj.assignee = assignee
      )

    #----------------------------------------------------------------------------
    # Closes a case
    #----------------------------------------------------------------------------
    close: (caseObj, note) ->
      return $http.post('/case/close/' + caseObj.id + '/', toFormData({note: note}), DEFAULT_POST_OPTS)
      .then(() ->
        caseObj.is_closed = true
      )

    #----------------------------------------------------------------------------
    # Re-opens a case
    #----------------------------------------------------------------------------
    reopen: (caseObj, note) ->
      return $http.post('/case/reopen/' + caseObj.id + '/', toFormData({note: note}), DEFAULT_POST_OPTS)
      .then(() ->
        caseObj.is_closed = false
      )

    #----------------------------------------------------------------------------
    # Re-labels a case
    #----------------------------------------------------------------------------
    relabel: (caseObj, labels) ->
      params = {
        labels: (l.id for l in labels)
      }

      return $http.post('/case/label/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS).then(() ->
        caseObj.labels = labels
      )

    #----------------------------------------------------------------------------
    # Updates a case's summary
    #----------------------------------------------------------------------------
    updateSummary: (caseObj, summary) ->
      params = {summary: summary}

      return $http.post('/case/update_summary/' + caseObj.id + '/', toFormData(params), DEFAULT_POST_OPTS).then(() ->
        caseObj.summary = summary
      )

    #----------------------------------------------------------------------------
    # Reply in a case
    #----------------------------------------------------------------------------
    replyTo: (caseObj, text) ->
      return $http.post('/case/reply/' + caseObj.id + '/', toFormData({text: text}), DEFAULT_POST_OPTS)

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
