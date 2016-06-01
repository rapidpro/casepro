# Unit tests for our Angular controllers

describe('controllers:', () ->
  $window = null
  $controller = null
  $rootScope = null
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

    jasmine.clock().install()

    test = {
      # users
      user1: {id: 101, name: "Tom McTest", partner: null},

      # labels
      tea: {id: 201, name: "Tea"},
      coffee: {id: 202, name: "Coffee"},

      # partners
      moh: {id: 301, name: "MOH"},
      who: {id: 302, name: "WHO"},

      # contacts
      contact1: {id: 401, name: "Ann"},
      contact2: {id: 402, name: "Bob"}
    }
  )

  afterEach(() ->
    jasmine.clock().uninstall()
  )

  #=======================================================================
  # Tests for DateRangeController
  #=======================================================================
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

  #=======================================================================
  # Tests for any controllers which must be children of HomeController
  #=======================================================================
  describe('home controllers:', () ->
    $homeScope = null
    $scope = null
    serverTime = 1464775597109  # ~ Jun 1st 2016 10:06:37 UTC

    beforeEach(() ->
      $window.contextData = {user: test.user1, partners: [], labels: [], groups: []}

      $homeScope = $rootScope.$new()
      $controller('HomeController', {$scope: $homeScope})

      $scope = $homeScope.$new()
    )

    #=======================================================================
    # Tests for CasesController
    #=======================================================================
    describe('CasesController', () ->
      CaseService = null

      beforeEach(inject((_CaseService_) ->
        CaseService = _CaseService_

        $controller('CasesController', {$scope: $scope})

        $homeScope.init('open', serverTime)
        $scope.init()

        # case test data
        test.case1 = {id: 601, summary: "Hi", opened_on: utcdate(2016, 5, 28, 10, 0)}
      ))

      it('loadOldItems', () ->
        fetchOld = spyOnPromise($q, $scope, CaseService, 'fetchOld')

        $scope.loadOldItems()

        expect(CaseService.fetchOld).toHaveBeenCalledWith({folder: 'open', assignee: null, label: null}, $scope.startTime, 1)

        fetchOld.resolve({results: [test.case1], hasMore: true})

        expect($scope.items).toEqual([test.case1])
        expect($scope.oldItemsMore).toEqual(true)
        expect($scope.isInfiniteScrollEnabled()).toEqual(true)
      )

      it('getItemFilter', () ->
        filter = $scope.getItemFilter()
        expect(filter({is_closed: false})).toEqual(true)
        expect(filter({is_closed: true})).toEqual(false)

        $scope.folder = 'closed'

        filter = $scope.getItemFilter()
        expect(filter({is_closed: false})).toEqual(false)
        expect(filter({is_closed: true})).toEqual(true)
      )

      it('onExportSearch', () ->
        confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
        startExport = spyOnPromise($q, $scope, CaseService, 'startExport')
        spyOn(UtilsService, 'displayAlert')

        $scope.onExportSearch()

        confirmModal.resolve()
        startExport.resolve()

        expect(CaseService.startExport).toHaveBeenCalledWith({folder: 'open', assignee: null, label: null})
        expect(UtilsService.displayAlert).toHaveBeenCalled()
      )
    )

    #=======================================================================
    # Tests for OutgoingController
    #=======================================================================
    describe('OutgoingController', () ->
      OutgoingService = null

      beforeEach(inject((_OutgoingService_) ->
        OutgoingService = _OutgoingService_

        $controller('OutgoingController', {$scope: $scope})

        $homeScope.init('sent', serverTime)
        $scope.init()

        # outgoing message test data
        test.out1 = {id: 601, text: "Hi", time: utcdate(2016, 5, 28, 10, 0)}
        test.out2 = {id: 602, text: "OK", time: utcdate(2016, 5, 27, 11, 0)}
        test.out3 = {id: 603, text: "Sawa", time: utcdate(2016, 5, 27, 12, 0)}
      ))

      it('loadOldItems', () ->
        fetchOld = spyOnPromise($q, $scope, OutgoingService, 'fetchOld')

        $scope.loadOldItems()

        expect(OutgoingService.fetchOld).toHaveBeenCalledWith({folder: 'sent', text: null, contact: null}, $scope.startTime, 1)

        fetchOld.resolve({results: [test.out3, test.out2], hasMore: true})

        expect($scope.items).toEqual([test.out3, test.out2])
        expect($scope.oldItemsMore).toEqual(true)
        expect($scope.isInfiniteScrollEnabled()).toEqual(true)

        fetchOld.reset()
        $scope.loadOldItems()

        fetchOld.resolve({results: [test.out1], hasMore: false})

        expect($scope.items).toEqual([test.out3, test.out2, test.out1])
        expect($scope.oldItemsMore).toEqual(false)
        expect($scope.isInfiniteScrollEnabled()).toEqual(false)
      )

      it('activateContact', () ->
        fetchOld = spyOnPromise($q, $scope, OutgoingService, 'fetchOld')

        $scope.activateContact(test.contact1)

        expect(OutgoingService.fetchOld).toHaveBeenCalledWith({folder: 'sent', text: null, contact: test.contact1}, $scope.startTime, 1)
      )

      it('onSearch', () ->
        fetchOld = spyOnPromise($q, $scope, OutgoingService, 'fetchOld')

        $scope.searchFields.text = "test"
        $scope.onSearch()

        expect(OutgoingService.fetchOld).toHaveBeenCalledWith({folder: 'sent', text: "test", contact: null}, $scope.startTime, 1)
      )
    )
  )

  #=======================================================================
  # Tests for PartnerController
  #=======================================================================
  describe('PartnerController', () ->
    PartnerService = null
    $scope = null

    beforeEach(inject((_PartnerService_) ->
      PartnerService = _PartnerService_

      $scope = $rootScope.$new()
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

  #=======================================================================
  # Tests for UserController
  #=======================================================================
  describe('UserController', () ->
    UserService = null
    $scope = null

    beforeEach(inject((_UserService_) ->
      UserService = _UserService_

      $scope = $rootScope.$new()
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