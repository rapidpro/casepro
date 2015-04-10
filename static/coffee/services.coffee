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
    constructor: ->
      @start_time = new Date()
      @old_last_page = 1

    #----------------------------------------------------------------------------
    # Fetches old messages for the given label
    #----------------------------------------------------------------------------
    fetchOldMessages: (labelId, page, searchParams, callback) ->
      params = {start_time: (formatIso8601 @start_time), page: page}

      # add search params
      params.text = searchParams.text
      params.after = formatIso8601(searchParams.after)
      params.before = formatIso8601(searchParams.before)
      params.groups = searchParams.groups
      params.reverse = searchParams.reverse

      $http.get '/label/messages/' + labelId + '/?' + $.param(params)
      .success (data) =>
        @_processMessages data.results
        callback(data.results, data.total, data.has_more)

    #----------------------------------------------------------------------------
    # Reply-to messages
    #----------------------------------------------------------------------------
    replyToMessages: (messages, message) ->
      action = if flagged then 'flag' else 'unflag'
      @_messagesAction messages, action, null

    #----------------------------------------------------------------------------
    # Flag or un-flag messages
    #----------------------------------------------------------------------------
    flagMessages: (messages, flagged) ->
      for msg in messages
        msg.flagged = flagged

      action = if flagged then 'flag' else 'unflag'
      @_messagesAction messages, action, null

    #----------------------------------------------------------------------------
    # Label messages
    #----------------------------------------------------------------------------
    labelMessages: (messages, label) ->
      without_label = []
      for msg in messages
        if label not in msg.labels
          without_label.push(msg)
          msg.labels.push(label)

      if without_label.length > 0
        @_messagesAction without_label, 'label', label

    #----------------------------------------------------------------------------
    # Archive messages
    #----------------------------------------------------------------------------
    archiveMessages: (messages) ->
      for msg in messages
        msg.archived = true

      @_messagesAction messages, 'archive', null

    #----------------------------------------------------------------------------
    # POSTs to the messages action endpoint
    #----------------------------------------------------------------------------
    _messagesAction: (messages, action, label) ->
      data = new FormData();
      data.append('message_ids', (msg.id for msg in messages))
      data.append('label', label)

      $http.post '/messages/' + action + '/', data, DEFAULT_POST_OPTS

    #----------------------------------------------------------------------------
    # Processes incoming messages
    #----------------------------------------------------------------------------
    _processMessages: (messages) ->
      for msg in messages
        # parse datetime string
        msg.time = parseIso8601 msg.time
        msg.archived = false
]


#=====================================================================
# Case service
#=====================================================================

services.factory 'CaseService', ['$rootScope', '$http', ($rootScope, $http) ->
  new class CaseService

    #----------------------------------------------------------------------------
    # Creates new case
    #----------------------------------------------------------------------------
    createNewCase: (message, callback) ->
      data = new FormData();
      data.append('message_id', message.id)
      data.append('labels', message.labels)

      $http.post '/case/create/', data, DEFAULT_POST_OPTS
      .success (data) ->
        callback(data.case_id)
]