services = angular.module('upartners.services', []);

#=====================================================================
# Date utilities
#=====================================================================
parse_iso8601 = (str) ->
  if str then new Date(Date.parse str) else null

format_iso8601 = (date) ->
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
    fetchOldMessages: (label_id, page, callback) ->
      params = {start_time: (format_iso8601 @start_time), page: page}

      $http.get '/label/messages/' + label_id + '/?' + $.param(params)
      .success (data) =>
        @_processMessages data.results
        callback(data.results, data.has_more)

    #=====================================================================
    # Flag or un-flag messages
    #=====================================================================
    flagMessages: (message_ids, flagged) ->
      action = if flagged then 'flag' else 'unflag'
      $http.post '/messages/' + action + '/?' + $.param({message_ids: message_ids})
      .error (data, status, headers, config) =>
        console.log(data)

    #=====================================================================
    # Processes incoming messages
    #=====================================================================
    _processMessages: (messages) ->
      for msg in messages
        # parse datetime string
        msg.time = parse_iso8601 msg.time
]
