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

  exports.toFormData = (params) ->
    data = new FormData()
    for own key, val of params
      if angular.isArray(val)
        val = (item.toString() for item in val).join(',')
      else if val
        val = val.toString()  # required for https://bugzilla.mozilla.org/show_bug.cgi?id=819328

      if val
        data.append(key, val)

    return data
)