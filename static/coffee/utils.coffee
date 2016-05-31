#=====================================================================
# Utilities
#=====================================================================

namespace = (target, name, block) ->
  [target, name, block] = [(exports ? window), arguments...] if arguments.length < 3
  top    = target
  target = target[item] ?= {} for item in name.split '.'
  block target, top

namespace('utils', (exports) ->
  exports.formatIso8601 = (date) ->
    if date then date.toISOString() else null
      
  exports.parseIso8601 = (str) ->
    if str then new Date(Date.parse str) else null
      
  exports.parseDates = (objects, propName) ->
    for obj in objects
      obj[propName] = exports.parseIso8601(obj[propName])
    return objects
)