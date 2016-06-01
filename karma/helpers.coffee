#
# helper for creating UTC datetimes
#
utcdate = (y, m, d, h, min, sec, ms) ->
  return new Date(Date.UTC(y, m - 1, d, h, min, sec, ms))

#
# helper for mocking service methods that return a promise, e.g.
#
# fetchBar = spyOnPromise($q, $scope, FooService, 'fetchBar')
#
# <do something which will wait for an fetchBar promise to be resolved>
#
# fetchBar.resolve("bar")
#
spyOnPromise = ($q, $scope, obj, method) ->
  deferred = $q.defer()
  spyOn(obj, method).and.returnValue(deferred.promise)

  return {
    reset: () ->
      deferred = $q.defer()
      obj[method].and.returnValue(deferred.promise)

    resolve: (value) ->
      deferred.resolve(value)
      $scope.$apply()
  }
