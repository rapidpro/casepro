# Unit tests for our Angular controllers (controllers listed A-Z)

describe('controllers:', () ->
  $window = null
  $controller = null
  $rootScope = null
  $scope = null
  $q = null
  UtilsService = null
  test = null

  beforeEach(() ->
    module('cases')

    inject((_$window_, _$controller_, _$rootScope_, _$q_, _UtilsService_) ->
      $window = _$window_
      $controller = _$controller_
      $rootScope = _$rootScope_
      $q = _$q_
      UtilsService = _UtilsService_
    )

    $scope = $rootScope.$new()  # each test gets a new scope
    jasmine.clock().install()

    test = {
      # users
      user1: {id: 101, name: "Tom McTest"},

      # labels
      tea: {id: 201, name: "Tea"},
      coffee: {id: 202, name: "Coffee"},

      # partners
      moh: {id: 301, name: "MOH"},
      who: {id: 302, name: "WHO"}
    }
  )

  afterEach(() ->
    jasmine.clock().uninstall()
  )
  
  describe('DateRangeController', () ->
    it('should not allow min to be greater than max', () ->
      jasmine.clock().mockDate(utcdate(2016, 1, 1, 11, 0, 0, 0));  # now is Jan 1st 2016 11:00 UTC

      $rootScope.range = {after: null, before: null}
      $scope = $rootScope.$new()

      $controller('DateRangeController', { $scope: $scope })
      $scope.init('range.after', 'range.before')

      expect($scope.afterOptions).toEqual({minDate: null, maxDate: utcdate(2016, 1, 1, 11, 0, 0, 0)})
      expect($scope.beforeOptions).toEqual({minDate: null, maxDate: utcdate(2016, 1, 1, 11, 0, 0, 0)})

      # after field is given a value
      $rootScope.range.after = utcdate(2015, 6, 1, 0, 0, 0, 0)  # Jun 1st 2015
      $scope.$digest()

      # value should become the min for before field
      expect($scope.beforeOptions).toEqual({minDate: utcdate(2015, 6, 1, 0, 0, 0, 0), maxDate: utcdate(2016, 1, 1, 11, 0, 0, 0)})

      # before field is given a value
      $rootScope.range.before = utcdate(2015, 8, 1, 0, 0, 0, 0)  # Aug 1st 2015
      $scope.$digest()

      # value should become the max for after field
      expect($scope.afterOptions).toEqual({minDate: null, maxDate: utcdate(2015, 8, 1, 0, 0, 0, 0)})
    )
  )

  describe('PartnerController', () ->
    PartnerService = null

    beforeEach(inject((_PartnerService_) ->
      PartnerService = _PartnerService_

      $window.contextData = {partner: test.moh}
      $controller('PartnerController', {$scope: $scope})
    ))

    it('onTabSelect', () ->
      expect($scope.users).toEqual([])
      expect($scope.usersFetched).toEqual(false)

      fetchUsers = spyOnPromise($q, $scope, PartnerService, 'fetchUsers')

      $scope.onTabSelect('users')

      users = [{id: 101, name: "Tom McTicket", replies: {last_month: 5, this_month: 10, total: 20}}]
      fetchUsers.resolve(users)

      expect($scope.users).toEqual(users)
      expect($scope.usersFetched).toEqual(true)

      # select the users tab again
      $scope.onTabSelect('users')

      # users shouldn't be re-fetched
      expect(PartnerService.fetchUsers.calls.count()).toEqual(1)
    )

    it('onDeletePartner', () ->
      confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
      deletePartner = spyOnPromise($q, $scope, PartnerService, 'delete')
      spyOn(UtilsService, 'navigate')

      $scope.onDeletePartner()

      confirmModal.resolve()
      deletePartner.resolve()

      expect(PartnerService.delete).toHaveBeenCalledWith(test.moh)
      expect(UtilsService.navigate).toHaveBeenCalledWith('/partner/')
    )
  )

  describe('UserController', () ->
    UserService = null

    beforeEach(inject((_UserService_) ->
      UserService = _UserService_

      $window.contextData = {user: test.user1}
      $controller('UserController', {$scope: $scope})
    ))

    it('onDeleteUser', () ->
      confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
      deleteUser = spyOnPromise($q, $scope, UserService, 'delete')
      spyOn(UtilsService, 'navigateBack')

      $scope.onDeleteUser()

      confirmModal.resolve()
      deleteUser.resolve()

      expect(UserService.delete).toHaveBeenCalledWith(test.user1)
      expect(UtilsService.navigateBack).toHaveBeenCalled()
    )
  )
)