#
# helper for creating UTC datetimes
#
utcdate = (y, m, d, h, min, sec, ms) ->
  return new Date(Date.UTC(y, m - 1, d, h, min, sec, ms))

#
# helper for mocking service methods that return a promise
#
spyOnPromise = ($q, scope, obj, method) ->
  deferred = $q.defer()
  spyOn(obj, method).and.returnValue(deferred.promise)
  return {
    resolve: (value) ->
      deferred.resolve(value)
      scope.$apply()
  }
