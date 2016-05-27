filters = angular.module('cases.filters', []);


#----------------------------------------------------------------------------
# Formats a date value in same style as GMail
#----------------------------------------------------------------------------
filters.filter('autodate', (dateFilter) ->
  (date) ->
    if angular.isString(date)
      date = utils.parseIso8601(date)

    now = new Date()
    isToday = date.getDate() == now.getDate() and date.getMonth() == now.getMonth() and date.getFullYear() == now.getFullYear()

    if isToday
      return dateFilter(date, 'HH:mm')
    else if date.getFullYear() == now.getFullYear()
      return dateFilter(date, 'MMM d')
    else
      return dateFilter(date, 'MMM d, yyyy')
)

#----------------------------------------------------------------------------
# Reverses an array of items
#----------------------------------------------------------------------------
filters.filter('reverse', () ->
  (items) ->
    return items.slice().reverse()
)
