filters = angular.module('cases.filters', []);


#----------------------------------------------------------------------------
# Formats a date value in same style as GMail
#----------------------------------------------------------------------------
filters.filter('autodate', (dateFilter) ->
  (date) ->
    now = new Date()
    isToday = date.getDate() == now.getDate() and date.getMonth() == now.getMonth() and date.getFullYear() == now.getFullYear()

    if isToday
      return dateFilter(date, 'HH:mm')
    else if date.getFullYear() == now.getFullYear()
      return dateFilter(date, 'MMM dd')
    else
      return dateFilter(date, 'MMM dd, yyyy')
)

#----------------------------------------------------------------------------
# Reverses an array of items
#----------------------------------------------------------------------------
filters.filter('reverse', () ->
  (items) ->
    items.slice().reverse()
)

#----------------------------------------------------------------------------
# String regex replacement
#----------------------------------------------------------------------------
filters.filter("replace", () ->
 (str, pattern, replacement) ->
    (str || '').replace(new RegExp(pattern, 'g'), (match, group) -> replacement)
)
