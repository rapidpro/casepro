#=====================================================================
# Utilities
#=====================================================================

namespace = (target, name, block) ->
  [target, name, block] = [(exports ? window), arguments...] if arguments.length < 3
  top    = target
  target = target[item] ?= {} for item in name.split '.'
  block target, top

namespace('utils', (exports) ->
  exports.formatIso8601 = (date, includeTime = true) ->
    if not date
      return null

    formatted = date.toISOString()

    if not includeTime
      formatted = formatted.split('T')[0]

    return formatted
      
  exports.parseIso8601 = (str) ->
    if str then new Date(Date.parse str) else null
      
  exports.parseDates = (objects, propName) ->
    for obj in objects
      obj[propName] = exports.parseIso8601(obj[propName])
    return objects

  exports.addMonths = (dateObj, num) ->
    currentMonth = dateObj.getMonth() + dateObj.getFullYear() * 12
    dateObj.setMonth(dateObj.getMonth() + num)
    diff = dateObj.getMonth() + dateObj.getFullYear() * 12 - currentMonth

    # if we don't get the right number, set date to last day of previous month
    if diff != num
        dateObj.setDate(0)

    return dateObj

  exports.findByProperty = (items, prop, value) ->
    for item in items
      if item[prop] == value
        return item
)