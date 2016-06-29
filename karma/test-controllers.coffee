# Unit tests for our Angular controllers

describe('controllers:', () ->
  $httpBackend = null
  $window = null
  $controller = null
  $rootScope = null
  $q = null
  UtilsService = null
  test = null

  beforeEach(() ->
    module('cases')

    inject((_$httpBackend_, _$window_, _$controller_, _$rootScope_, _$q_, _UtilsService_) ->
      $httpBackend = _$httpBackend_
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
      ann: {id: 401, name: "Ann"},
      bob: {id: 402, name: "Bob"}
    }
  )

  afterEach(() ->
    jasmine.clock().uninstall()
  )

  #=======================================================================
  # Tests for CaseController
  #=======================================================================
  describe('CaseController', () ->
    CaseService = null
    ContactService = null
    $scope = null

    beforeEach(() ->
      inject((_CaseService_, _ContactService_) ->
        CaseService = _CaseService_
        ContactService = _ContactService_
      )

      $window.contextData = {all_labels: [test.tea, test.coffee], all_partners: [test.moh, test.who]}

      $scope = $rootScope.$new()
      $controller('CaseController', {$scope: $scope})

      # extra test data
      test.case1 = {id: 601, contact: test.ann, summary: "Hi", opened_on: utcdate(2016, 5, 28, 10, 0)}
    )

    it('should initialize correctly', () ->
      fetchCase = spyOnPromise($q, $scope, CaseService, 'fetchSingle')
      fetchContact = spyOnPromise($q, $scope, ContactService, 'fetch')

      $scope.init(601, 140)

      expect($scope.caseId).toEqual(601)
      expect($scope.msgCharsRemaining).toEqual(140)

      fetchCase.resolve(test.case1)
      fetchContact.resolve(test.ann)

      expect($scope.caseObj).toEqual(test.case1)
      expect($scope.contact).toEqual(test.ann)
    )

    it('addNote', () ->
      noteModal = spyOnPromise($q, $scope, UtilsService, 'noteModal')
      addNote = spyOnPromise($q, $scope, CaseService, 'addNote')

      $scope.caseObj = test.case1
      $scope.onAddNote()

      noteModal.resolve("this is a note")
      addNote.resolve()

      expect(UtilsService.noteModal).toHaveBeenCalled()
      expect(CaseService.addNote).toHaveBeenCalledWith(test.case1, "this is a note")
    )

    it('onWatch', () ->
      confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
      watchCase = spyOnPromise($q, $scope, CaseService, 'watch')

      $scope.caseObj = test.case1
      $scope.onWatch()

      confirmModal.resolve()
      watchCase.resolve()

      expect(UtilsService.confirmModal).toHaveBeenCalled()
      expect(CaseService.watch).toHaveBeenCalledWith(test.case1)
    )

    it('onUnwatch', () ->
      confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
      unwatchCase = spyOnPromise($q, $scope, CaseService, 'unwatch')

      $scope.caseObj = test.case1
      $scope.onUnwatch()

      confirmModal.resolve()
      unwatchCase.resolve()

      expect(UtilsService.confirmModal).toHaveBeenCalled()
      expect(CaseService.unwatch).toHaveBeenCalledWith(test.case1)
    )
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
    # injected services
    MessageService = null
    OutgoingService = null
    CaseService = null

    $homeScope = null
    $scope = null
    serverTime = 1464775597109  # ~ Jun 1st 2016 10:06:37 UTC

    beforeEach(() ->
      inject((_MessageService_, _OutgoingService_, _CaseService_) ->
        MessageService = _MessageService_
        OutgoingService = _OutgoingService_
        CaseService = _CaseService_
      )

      $window.contextData = {user: test.user1, partners: [], labels: [test.tea, test.coffee], groups: []}

      $homeScope = $rootScope.$new()
      $controller('HomeController', {$scope: $homeScope})

      $scope = $homeScope.$new()
    )

    #=======================================================================
    # Tests for CasesController
    #=======================================================================
    describe('CasesController', () ->

      beforeEach(() ->
        $controller('CasesController', {$scope: $scope})

        $homeScope.init('open', serverTime)
        $scope.init()

        # extra test data
        test.case1 = {id: 601, summary: "Hi", opened_on: utcdate(2016, 5, 28, 10, 0)}
      )

      it('loadOldItems', () ->
        fetchOld = spyOnPromise($q, $scope, CaseService, 'fetchOld')

        $scope.loadOldItems()

        expect(CaseService.fetchOld).toHaveBeenCalledWith({folder: 'open', assignee: null, label: null}, $scope.startTime, 1)

        fetchOld.resolve({results: [test.case1], hasMore: true})

        expect($scope.items).toEqual([test.case1])
        expect($scope.oldItemsMore).toEqual(true)
        expect($scope.isInfiniteScrollEnabled()).toEqual(true)
      )

      it('loadOldItems should report to raven on failure', () ->
        spyOn(CaseService, 'fetchOld').and.callThrough()
        spyOn(UtilsService, 'displayAlert')
        spyOn(Raven, 'captureMessage')

        $httpBackend.expectGET(/\/case\/search\/\?.*/).respond(() -> [500, 'Server error', {}, 'Internal error'])

        $scope.loadOldItems()

        $httpBackend.flush()
        expect(UtilsService.displayAlert).toHaveBeenCalled()
        expect(Raven.captureMessage).toHaveBeenCalled()
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
    # Tests for MessagesController
    #=======================================================================
    describe('MessagesController', () ->

      beforeEach(() ->
        $controller('MessagesController', {$scope: $scope})

        $homeScope.init('inbox', serverTime)
        $scope.init()

        # extra test data
        test.msg1 = {id: 101, text: "Hello 1", labels: [test.tea], flagged: true, archived: false}
        test.msg2 = {id: 102, text: "Hello 2", labels: [test.coffee], flagged: false, archived: false}
        test.msg3 = {id: 103, text: "Hello 3", labels: [], flagged: false, archived: false}
      )

      it('should initialize correctly', () ->
        expect($scope.items).toEqual([])
        expect($scope.activeLabel).toEqual(null)
        expect($scope.activeContact).toEqual(null)
        expect($scope.inactiveLabels).toEqual([test.tea, test.coffee])
      )

      it('loadOldItems', () ->
        fetchOld = spyOnPromise($q, $scope, MessageService, 'fetchOld')

        $scope.loadOldItems()

        expect(MessageService.fetchOld).toHaveBeenCalledWith({
          folder: 'inbox', label: null, contact: null, text: null,
          groups: [], archived: false, after: null, before: null
        }, $scope.startTime, 1)

        fetchOld.resolve({results: [test.msg3, test.msg2], hasMore: true})

        expect($scope.items).toEqual([test.msg3, test.msg2])
        expect($scope.oldItemsMore).toEqual(true)
        expect($scope.isInfiniteScrollEnabled()).toEqual(true)
      )

      it('getItemFilter', () ->
        filter = $scope.getItemFilter()
        expect(filter({archived: false})).toEqual(true)
        expect(filter({archived: true})).toEqual(false)

        $scope.folder = 'flagged'
        $scope.searchFields.archived = false

        filter = $scope.getItemFilter()
        expect(filter({flagged: true, archived: false})).toEqual(true)
        expect(filter({flagged: true, archived: true})).toEqual(false)
        expect(filter({flagged: false})).toEqual(false)

        $scope.searchFields.archived = true

        filter = $scope.getItemFilter()
        expect(filter({flagged: true, archived: false})).toEqual(true)
        expect(filter({flagged: true, archived: true})).toEqual(true)
        expect(filter({flagged: false})).toEqual(false)

        $scope.folder = 'archived'

        filter = $scope.getItemFilter()
        expect(filter({archived: false})).toEqual(false)
        expect(filter({archived: true})).toEqual(true)

        $scope.folder = 'unlabelled'

        filter = $scope.getItemFilter()
        expect(filter({labels: []})).toEqual(true)
        expect(filter({labels: [test.tea]})).toEqual(false)
      )

      it('onExportSearch', () ->
        confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
        startExport = spyOnPromise($q, $scope, MessageService, 'startExport')
        spyOn(UtilsService, 'displayAlert')

        $scope.onExportSearch()

        confirmModal.resolve()
        startExport.resolve()

        expect(MessageService.startExport).toHaveBeenCalledWith({
          folder: 'inbox', label: null, contact: null, text: null,
          groups: [], archived: false, after: null, before: null
        })
        expect(UtilsService.displayAlert).toHaveBeenCalled()
      )

      it('onFlagSelection', () ->
        confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
        bulkFlag = spyOnPromise($q, $scope, MessageService, 'bulkFlag')

        $scope.selection = [test.msg1]
        $scope.onFlagSelection()

        confirmModal.resolve()
        bulkFlag.resolve()

        expect(MessageService.bulkFlag).toHaveBeenCalledWith([test.msg1], true)
      )

      it('onArchiveSelection', () ->
        confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
        bulkArchive = spyOnPromise($q, $scope, MessageService, 'bulkArchive')

        $scope.selection = [test.msg1]
        $scope.onArchiveSelection()

        confirmModal.resolve()
        bulkArchive.resolve()

        expect(MessageService.bulkArchive).toHaveBeenCalledWith([test.msg1])
      )

      it('onRestoreSelection', () ->
        confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
        bulkRestore = spyOnPromise($q, $scope, MessageService, 'bulkRestore')

        $scope.selection = [test.msg1]
        $scope.onRestoreSelection()

        confirmModal.resolve()
        bulkRestore.resolve()

        expect(MessageService.bulkRestore).toHaveBeenCalledWith([test.msg1])
      )

      describe('onCaseFromMessage', () ->
        it('should open new case if message does not have one', () ->
          newCaseModal = spyOnPromise($q, $scope, UtilsService, 'newCaseModal')
          openCase = spyOnPromise($q, $scope, CaseService, 'open')
          spyOn(UtilsService, 'navigate')

          $scope.onCaseFromMessage(test.msg1)

          newCaseModal.resolve({summary: "New case", assignee: test.moh})
          openCase.resolve({id: 601, summary: "New case", isNew: false})

          expect(CaseService.open).toHaveBeenCalledWith(test.msg1, "New case", test.moh)
          expect(UtilsService.navigate).toHaveBeenCalledWith('/case/read/601/?alert=open_found_existing')
        )

        it('should redirect to an existing case', () ->
          spyOn(UtilsService, 'navigate')

          test.msg1.case = {id: 601, summary: "A case"}
          $scope.onCaseFromMessage(test.msg1)

          expect(UtilsService.navigate).toHaveBeenCalledWith('/case/read/601/')
        )
      )

      it('onForwardMessage', () ->
        composeModal = spyOnPromise($q, $scope, UtilsService, 'composeModal')
        forward = spyOnPromise($q, $scope, MessageService, 'forward')
        spyOn(UtilsService, 'displayAlert')

        $scope.onForwardMessage(test.msg1)

        composeModal.resolve({text: "FYI", urn: "tel:+260964153686"})
        forward.resolve()

        expect(MessageService.forward).toHaveBeenCalledWith(test.msg1, "FYI", "tel:+260964153686")
        expect(UtilsService.displayAlert).toHaveBeenCalled()
      )

      it('onLabelMessage', () ->
        labelModal = spyOnPromise($q, $scope, UtilsService, 'labelModal')
        relabel = spyOnPromise($q, $scope, MessageService, 'relabel')

        $scope.onLabelMessage(test.msg1)

        labelModal.resolve([test.coffee])
        relabel.resolve()

        expect(MessageService.relabel).toHaveBeenCalledWith(test.msg1, [test.coffee])
      )

      it('onToggleMessageFlag', () ->
        confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
        bulkFlag = spyOnPromise($q, $scope, MessageService, 'bulkFlag')

        # try with message that is currently flagged
        $scope.onToggleMessageFlag(test.msg1)

        confirmModal.resolve()
        bulkFlag.resolve()

        expect(MessageService.bulkFlag).toHaveBeenCalledWith([test.msg1], false)

        confirmModal.reset()

        # try with message that isn't currently flagged
        $scope.onToggleMessageFlag(test.msg2)

        confirmModal.resolve()
        bulkFlag.resolve()

        expect(MessageService.bulkFlag).toHaveBeenCalledWith([test.msg2], true)
      )
    )

    #=======================================================================
    # Tests for OutgoingController
    #=======================================================================
    describe('OutgoingController', () ->

      beforeEach(() ->
        $controller('OutgoingController', {$scope: $scope})

        $homeScope.init('sent', serverTime)
        $scope.init()

        # outgoing message test data
        test.out1 = {id: 601, text: "Hi", time: utcdate(2016, 5, 28, 10, 0)}
        test.out2 = {id: 602, text: "OK", time: utcdate(2016, 5, 27, 11, 0)}
        test.out3 = {id: 603, text: "Sawa", time: utcdate(2016, 5, 27, 12, 0)}
      )

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
        expect($scope.hasTooManyItemsToDisplay()).toEqual(false)
      )

      it('activateContact', () ->
        fetchOld = spyOnPromise($q, $scope, OutgoingService, 'fetchOld')

        $scope.activateContact(test.ann)

        expect(OutgoingService.fetchOld).toHaveBeenCalledWith({folder: 'sent', text: null, contact: test.ann}, $scope.startTime, 1)
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
      expect($scope.initialisedTabs).toEqual([])

      fetchUsers = spyOnPromise($q, $scope, PartnerService, 'fetchUsers')
      fetchRepliesChart = spyOnPromise($q, $scope, PartnerService, 'fetchRepliesChart')

      $scope.onTabSelect('summary')

      expect(PartnerService.fetchRepliesChart).toHaveBeenCalledWith(test.moh)
      expect($scope.initialisedTabs).toEqual(['summary'])

      $scope.onTabSelect('users')

      users = [{id: 101, name: "Tom McTicket", replies: {last_month: 5, this_month: 10, total: 20}}]
      fetchUsers.resolve(users)

      expect($scope.users).toEqual(users)
      expect($scope.initialisedTabs).toEqual(['summary', 'users'])

      # select the users tab again
      $scope.onTabSelect('users')

      # users shouldn't be re-fetched
      expect(PartnerService.fetchUsers.calls.count()).toEqual(1)
      expect($scope.initialisedTabs).toEqual(['summary', 'users'])
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