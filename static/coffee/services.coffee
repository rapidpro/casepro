services = angular.module('upartners.services', []);

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

    #=====================================================================
    # Fetches old messages for the given label
    #=====================================================================
    fetchOldMessages: (labelId, page, searchParams, callback) ->
      params = {start_time: (formatIso8601 @start_time), page: page}

      # add search params
      params.text = searchParams.text
      params.after = formatIso8601(searchParams.after)
      params.before = formatIso8601(searchParams.before)
      params.groups = searchParams.groups

      $http.get '/label/messages/' + labelId + '/?' + $.param(params)
      .success (data) =>
        @_processMessages data.results
        callback(data.results, data.has_more)

    #=====================================================================
    # Flag or un-flag messages
    #=====================================================================
    flagMessages: (messages, flagged) ->
      for msg in messages
        msg.flagged = flagged

      action = if flagged then 'flag' else 'unflag'
      $http.post '/messages/' + action + '/?' + $.param({message_ids: (msg.id for msg in messages)})

    #=====================================================================
    # Label messages
    #=====================================================================
    labelMessages: (messages, labelUuid) ->
      for msg in messages
        msg.flagged = flagged

      $http.post '/messages/label/?' + $.param({message_ids: (msg.id for msg in messages)})

    #=====================================================================
    # Archive messages
    #=====================================================================
    archiveMessages: (messages) ->
      for msg in messages
        msg.archived = true

      $http.post '/messages/archive/?' + $.param({message_ids: (msg.id for msg in messages)})

    #=====================================================================
    # Processes incoming messages
    #=====================================================================
    _processMessages: (messages) ->
      for msg in messages
        # parse datetime string
        msg.time = parseIso8601 msg.time
        msg.archived = false
]
