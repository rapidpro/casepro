# Unit tests for our Angular controllers (controllers listed A-Z)

describe('controllers:', () ->
  $rootScope = null
  $controller = null

  beforeEach(() ->
    module('cases')

    inject((_$rootScope_, _$controller_) ->
      $rootScope = _$rootScope_
      $controller = _$controller_
    )
  )
  
  describe('DateRangeController', () ->
    it('should not allow min to be greater than max', () ->
      $scope = $rootScope.$new()
      $scope.range = {after: null, before: null}

      $controller('DateRangeController', { $scope: $scope })
      $scope.init('range.after', 'range.before')

      $scope.range.after = utcdate(2015, 1, 1, 10, 0, 0, 0)
      $scope.$digest()

      expect($scope.beforeOptions.minDate).toEqual(utcdate(2015, 1, 1, 10, 0, 0, 0))

      $scope.range.before = utcdate(2016, 1, 1, 10, 0, 0, 0)
      $scope.$digest()

      expect($scope.afterOptions.maxDate).toEqual(utcdate(2016, 1, 1, 10, 0, 0, 0))
    )
  )
)