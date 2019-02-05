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

      # fields
      nickname: {key: 'nickname', label: "Nickname", value_type: 'T'},
      age: {key: 'age', label: "Age", value_type: 'N'},

      # groups
      females: {id: 701, name: "Females"},
      males: {id: 702, name: "Males"},
      ureporters: {id: 703, name: "U-Reporters"},

      # contacts
      ann: {id: 401, name: "Ann", fields: {'age': 35}, groups: [{id: 701, name: "Females"}, {id: 703, name: "U-Reporters"}], urns: []},
      bob: {id: 402, name: "Bob", fields: {}, groups: []}

      # language
      language1: {code: "eng", name: "English"},
      language2: {code: "afr", name: "Afrikaans"},

      # FAQs
      faq1: {id: 401, question: "Am I pregnant?", answer: "yes", language: {code: "eng", name: "English"}, labels: [{id: 201, name: "Tea"}, {id: 202, name: "Coffee"}], parent: null},
      faq2: {id: 402, question: "Can I drink coffee?", answer: "no", language: {code: "eng", name: "English"}, labels: [{id: 201, name: "Tea"}, {id: 202, name: "Coffee"}], parent: null},

      # translation
      translation1: {id: 601, question: "Is ek swanger", answer: "ja", language: {code: "afr", name: "Afrikaans"}, labels: {id: 201, name: "Tea"}, parent: 401},
      translation2: {id: 602, question: "Is ek swanger", answer: "ja", language: {code: "afr", name: "Afrikaans"}, labels: {id: 201, name: "Tea"}, parent: 402},
      translation3: {id: 603, question: "Curabitur blandit.", answer: "Lorem", language: {code: "ale", name: "Aleut"}, labels: {id: 201, name: "Tea"}, parent: 402},
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
    PartnerService = null
    UserService = null
    $scope = null

    beforeEach(() ->
      inject((_CaseService_, _ContactService_, _PartnerService_, _UserService_) ->
        CaseService = _CaseService_
        ContactService = _ContactService_
        PartnerService = _PartnerService_
        UserService = _UserService_
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

    it('should should proxy timelineChanged events from child scopes', (done) ->
      child = $scope.$new(false)
      sibling = $scope.$new(false)

      sibling.$on('timelineChanged', -> done())
      child.$emit('timelineChanged')
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

    it('onReassign', () ->
      reassignModal = spyOnPromise($q, $scope, UtilsService, 'assignModal')
      reassignCase = spyOnPromise($q, $scope, CaseService, 'reassign')
      partnerFetch = spyOnPromise($q, $scope, PartnerService, 'fetchAll')

      $scope.caseObj = test.case1
      $scope.onReassign()

      partnerFetch.resolve([test.moh, test.who])
      reassignModal.resolve({assignee: test.moh, user: test.user1})
      reassignCase.resolve()

      # List of partners should be fetched
      expect(PartnerService.fetchAll).toHaveBeenCalled()
      # Modal should be sent list of partners and list of users for first partner
      expect(UtilsService.assignModal).toHaveBeenCalledWith('Re-assign', null, [test.moh, test.who])
      # Result of modal selection should be sent to reassign the case
      expect(CaseService.reassign).toHaveBeenCalledWith(test.case1, test.moh, test.user1)
    )

    it('should should add a alert on alert events', () ->
      $scope.alerts = []
      $scope.$emit('alert', {type: 'foo'})
      expect($scope.alerts).toEqual([{type: 'foo'}])
    )

    it('should should ignore duplicate pod_load_api_failure alerts', () ->
      $scope.alerts = []

      $scope.$emit('alert', {type: 'pod_load_api_failure'})
      expect($scope.alerts).toEqual([{type: 'pod_load_api_failure'}])

      $scope.$emit('alert', {type: 'pod_load_api_failure'})
      $scope.$emit('alert', {type: 'pod_load_api_failure'})
      expect($scope.alerts).toEqual([{type: 'pod_load_api_failure'}])
    )

    describe('addAlert', () ->
      it('should add the given alert', () ->
        $scope.alerts = []
        $scope.addAlert({type: 'foo'})
        expect($scope.alerts).toEqual([{type: 'foo'}])
      )
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
  # Tests for any controllers which must be children of InboxController
  #=======================================================================
  describe('inbox controllers:', () ->
    # injected services
    MessageService = null
    OutgoingService = null
    CaseService = null
    PartnerService = null
    UserService = null
    ModalService = null
    LabelService = null

    $inboxScope = null
    $scope = null
    serverTime = 1464775597109  # ~ Jun 1st 2016 10:06:37 UTC

    beforeEach(() ->
      inject((_MessageService_, _OutgoingService_, _CaseService_, _PartnerService_, _UserService_, _ModalService_, _LabelService_) ->
        MessageService = _MessageService_
        OutgoingService = _OutgoingService_
        CaseService = _CaseService_
        PartnerService = _PartnerService_
        UserService = _UserService_
        ModalService = _ModalService_
        LabelService = _LabelService_
      )

      $window.contextData = {user: test.user1, partners: [], labels: [test.tea, test.coffee], groups: []}

      $inboxScope = $rootScope.$new()
      $controller('InboxController', {$scope: $inboxScope})

      $scope = $inboxScope.$new()
    )

    #=======================================================================
    # Tests for CasesController
    #=======================================================================
    describe('CasesController', () ->

      beforeEach(() ->
        fetchPartners = spyOnPromise($q, $scope, PartnerService, 'fetchAll')

        $controller('CasesController', {$scope: $scope})

        $inboxScope.init('open', serverTime)
        $scope.init()

        fetchPartners.resolve([test.moh, test.who])

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

      it('loadOldItems should display alert on failure', () ->
        spyOn(CaseService, 'fetchOld').and.callThrough()
        spyOn(UtilsService, 'displayAlert')

        $httpBackend.expectGET(/\/case\/search\/\?.*/).respond(() -> [500, 'Server error', {}, 'Internal error'])

        $scope.loadOldItems()

        $httpBackend.flush()
        expect(UtilsService.displayAlert).toHaveBeenCalled()
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
      $intervalSpy = null

      beforeEach(() ->
        inject((_$interval_) ->
          $intervalSpy = jasmine.createSpy('$interval', _$interval_).and.callThrough()
        )
        
        $controller('MessagesController', {$scope: $scope, $interval: $intervalSpy})

        $inboxScope.init('inbox', serverTime)
        $scope.init()
        
        $scope.lastPollTime = utcdate(2016, 1, 2, 3, 0, 0, 0)
        jasmine.clock().mockDate($scope.lastPollTime)

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
        
        expect($scope.pollBusy).toEqual(false)
        expect($scope.lastPollTime).toEqual(utcdate(2016, 1, 2, 3, 0, 0, 0))
        expect($intervalSpy).toHaveBeenCalledWith($scope.poll, 10000)
      )

      it('loadOldItems', () ->
        fetchOld = spyOnPromise($q, $scope, MessageService, 'fetchOld')

        $scope.loadOldItems()

        expect(MessageService.fetchOld).toHaveBeenCalledWith({
          folder: 'inbox', label: null, contact: null, text: null, archived: false, after: null, before: null
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
          folder: 'inbox', label: null, contact: null, text: null, archived: false, after: null, before: null
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
          fetchPartners = spyOnPromise($q, $scope, PartnerService, 'fetchAll')
          checkLock = spyOnPromise($q, $scope, MessageService, 'checkLock')
          newCaseModal = spyOnPromise($q, $scope, UtilsService, 'newCaseModal')
          openCase = spyOnPromise($q, $scope, CaseService, 'open')
          spyOn(UtilsService, 'navigate')

          $scope.onCaseFromMessage(test.msg1)

          fetchPartners.resolve([test.moh, test.who])
          checkLock.resolve({items: 101})
          newCaseModal.resolve({summary: "New case", assignee: test.moh, user: test.user1})
          openCase.resolve({id: 601, summary: "New case", isNew: false})

          expect(MessageService.checkLock).toHaveBeenCalledWith([test.msg1])
          expect(CaseService.open).toHaveBeenCalledWith(test.msg1, "New case", test.moh, test.user1)
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
        checkLock = spyOnPromise($q, $scope, MessageService, 'checkLock')
        composeModal = spyOnPromise($q, $scope, UtilsService, 'composeModal')
        forward = spyOnPromise($q, $scope, MessageService, 'forward')
        spyOn(UtilsService, 'displayAlert')

        $scope.onForwardMessage(test.msg1)

        checkLock.resolve({items: 101})
        composeModal.resolve({text: "FYI", urn: "tel:+260964153686"})
        forward.resolve()

        expect(MessageService.checkLock).toHaveBeenCalledWith([test.msg1])
        expect(MessageService.forward).toHaveBeenCalledWith(test.msg1, "FYI", "tel:+260964153686")
        expect(UtilsService.displayAlert).toHaveBeenCalled()
      )

      it('onLabelMessage', () ->
        labelModal = spyOnPromise($q, $scope, UtilsService, 'labelModal')
        relabel = spyOnPromise($q, $scope, MessageService, 'relabel')
        label = spyOnPromise($q, $scope, LabelService, 'fetchAll')

        $scope.onLabelMessage(test.msg1)

        labelModal.resolve([test.coffee])
        relabel.resolve()
        label.resolve()

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

      it('onCaseWithoutMessage existing case', () ->
        createCaseModal = spyOnPromise($q, $scope, ModalService, 'createCase')
        openCase = spyOnPromise($q, $scope, CaseService, 'open')
        redirect = spyOnPromise($q, $scope, UtilsService, 'navigate')

        $scope.onCaseWithoutMessage()
        expect(ModalService.createCase).toHaveBeenCalledWith({title: 'Open Case'})

        createCaseModal.resolve({text: 'test summary', partner: 2, user: 3, urn: 'tel:123'})
        expect(CaseService.open).toHaveBeenCalledWith(null, 'test summary', 2, 3, 'tel:123')

        openCase.resolve({is_new: false, id: 7})
        expect(UtilsService.navigate).toHaveBeenCalledWith('case/read/7/?alert=open_found_existing')
      )

      it('onCaseWithoutMessage no existing case', () ->
        createCaseModal = spyOnPromise($q, $scope, ModalService, 'createCase')
        openCase = spyOnPromise($q, $scope, CaseService, 'open')
        redirect = spyOnPromise($q, $scope, UtilsService, 'navigate')

        $scope.onCaseWithoutMessage()
        expect(ModalService.createCase).toHaveBeenCalledWith({title: 'Open Case'})

        createCaseModal.resolve({text: 'test summary', partner: 2, user: 3, urn: 'tel:123'})
        expect(CaseService.open).toHaveBeenCalledWith(null, 'test summary', 2, 3, 'tel:123')

        openCase.resolve({is_new: true, id: 7})
        expect(UtilsService.navigate).toHaveBeenCalledWith('case/read/7/')
      )
    )

    #=======================================================================
    # Tests for OutgoingController
    #=======================================================================
    describe('OutgoingController', () ->

      beforeEach(() ->
        $controller('OutgoingController', {$scope: $scope})

        $inboxScope.init('sent', serverTime)
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
  # Tests for ContactController
  #=======================================================================
  describe('ContactController', () ->
    ContactService = null
    $scope = null

    beforeEach(inject((_ContactService_) ->
      ContactService = _ContactService_

      $scope = $rootScope.$new()
      $window.contextData = {contact: test.ann, fields: [test.age, test.nickname]}
      $controller('ContactController', {$scope: $scope})
    ))

    it('init should fetch contact cases', () ->
      expect($scope.contact).toEqual(test.ann)
      expect($scope.fields).toEqual([test.age, test.nickname])

      fetchCases = spyOnPromise($q, $scope, ContactService, 'fetchCases')

      $scope.init()

      cases = [{id: 501, opened_on: utcdate(2016, 5, 17, 8, 49, 13, 698)}]
      fetchCases.resolve(cases)

      expect(ContactService.fetchCases).toHaveBeenCalledWith(test.ann)
      expect($scope.cases).toEqual(cases)
    )

    it('getGroups', () ->
      expect($scope.getGroups()).toEqual("Females, U-Reporters")
    )
  )

  #=======================================================================
  # Tests for FaqController
  #=======================================================================
  describe('FaqController', () ->
    FaqService = null
    UtilsService = null
    $scope = null

    beforeEach(inject((_FaqService_) ->
      FaqService = _FaqService_

      $scope = $rootScope.$new()
      $window.contextData = {faq: test.faq1}
      $controller('FaqController', {$scope: $scope})
    ))

    it('init should fetch all translations', () ->
      fetchAllFaqs = spyOnPromise($q, $scope, FaqService, 'fetchAllFaqs')

      $scope.init()

      fetchAllFaqs.resolve([test.translation1, test.translation2])

      expect(FaqService.fetchAllFaqs).toHaveBeenCalled()
      expect($scope.translations).toEqual([test.translation1, test.translation2])
    )

    it('onDeleteFaq', () ->
      confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
      deleteFaq = spyOnPromise($q, $scope, FaqService, 'delete')
      spyOn(UtilsService, 'navigate')

      $scope.onDeleteFaq()

      confirmModal.resolve()
      deleteFaq.resolve()

      expect(FaqService.delete).toHaveBeenCalledWith(test.faq1)
      expect(UtilsService.navigate).toHaveBeenCalledWith('/faq/')
    )

    it('onDeleteFaqTranslation', () ->
      confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
      deleteTranslation = spyOnPromise($q, $scope, FaqService, 'deleteTranslation')
      spyOn(UtilsService, 'navigate')

      $scope.onDeleteFaqTranslation(test.translation1)

      confirmModal.resolve()
      deleteTranslation.resolve()

      expect(FaqService.deleteTranslation).toHaveBeenCalledWith(test.translation1)
      expect(UtilsService.navigate).toHaveBeenCalledWith('')
    )

    it('onNewTranslation', () ->
      faqModal = spyOnPromise($q, $scope, UtilsService, 'faqModal')
      createFaq = spyOnPromise($q, $scope, FaqService, 'createFaq')
      spyOn(UtilsService, 'navigate')

      $scope.onNewTranslation()

      faqModal.resolve(test.translation1)
      createFaq.resolve()

      expect(FaqService.createFaq).toHaveBeenCalledWith(test.translation1)
      expect(UtilsService.navigate).toHaveBeenCalledWith('')
    )

    it('onEditTranslation', () ->
      faqModal = spyOnPromise($q, $scope, UtilsService, 'faqModal')
      updateFaq = spyOnPromise($q, $scope, FaqService, 'updateFaq')
      spyOn(UtilsService, 'navigate')

      $scope.onEditTranslation(test.translation1, test.faq1)

      faqModal.resolve(test.translation1)
      updateFaq.resolve()

      expect(FaqService.updateFaq).toHaveBeenCalledWith(test.translation1)
      expect(UtilsService.navigate).toHaveBeenCalledWith('')
    )

    it('onEditFaq', () ->
      faqModal = spyOnPromise($q, $scope, UtilsService, 'faqModal')
      updateFaq = spyOnPromise($q, $scope, FaqService, 'updateFaq')
      spyOn(UtilsService, 'navigate')

      $scope.onEditFaq()

      faqModal.resolve(test.faq1)
      updateFaq.resolve()

      expect(FaqService.updateFaq).toHaveBeenCalledWith(test.faq1)
      expect(UtilsService.navigate).toHaveBeenCalledWith('')
    )
  )

  #=======================================================================
  # Tests for FaqListController
  #=======================================================================
  describe('FaqListController', () ->
    FaqService = null
    UtilsService = null
    $scope = null

    beforeEach(inject((_FaqService_) ->
      FaqService = _FaqService_

      $scope = $rootScope.$new()
      $controller('FaqListController', {$scope: $scope})
    ))

    it('init should fetch all FAQs', () ->
      fetchAllFaqs = spyOnPromise($q, $scope, FaqService, 'fetchAllFaqs')

      $scope.init()

      fetchAllFaqs.resolve([test.faq1, test.faq2])

      expect(FaqService.fetchAllFaqs).toHaveBeenCalled()
      expect($scope.faqs).toEqual([test.faq1, test.faq2])
    )


    it('onNewFaq', () ->
      faqModal = spyOnPromise($q, $scope, UtilsService, 'faqModal')
      createFaq = spyOnPromise($q, $scope, FaqService, 'createFaq')
      spyOn(UtilsService, 'navigate')


      $scope.onNewFaq(test.faq1)

      faqModal.resolve(test.faq1)
      createFaq.resolve()

      expect(FaqService.createFaq).toHaveBeenCalledWith(test.faq1)
      expect(UtilsService.navigate).toHaveBeenCalledWith('')
    )
  )

  #=======================================================================
  # Tests for HomeController
  #=======================================================================
  describe('HomeController', () ->
    StatisticsService = null
    PartnerService = null
    LabelService = null
    UserService = null
    $scope = null

    beforeEach(inject((_StatisticsService_, _PartnerService_, _LabelService_, _UserService_) ->
      StatisticsService = _StatisticsService_
      PartnerService = _PartnerService_
      LabelService = _LabelService_
      UserService = _UserService_

      $scope = $rootScope.$new()
      $controller('HomeController', {$scope: $scope})
    ))

    it('onTabSelect', () ->
      repliesChart = spyOnPromise($q, $scope, StatisticsService, 'repliesChart')
      incomingChart = spyOnPromise($q, $scope, StatisticsService, 'incomingChart')
      labelsPieChart = spyOnPromise($q, $scope, StatisticsService, 'labelsPieChart')
      fetchPartners = spyOnPromise($q, $scope, PartnerService, 'fetchAll')
      fetchLabels = spyOnPromise($q, $scope, LabelService, 'fetchAll')
      fetchUsers = spyOnPromise($q, $scope, UserService, 'fetchNonPartner')

      $scope.onTabSelect(0)

      expect(StatisticsService.repliesChart).toHaveBeenCalledWith()
      expect(StatisticsService.incomingChart).toHaveBeenCalledWith()
      expect(StatisticsService.labelsPieChart).toHaveBeenCalledWith()

      $scope.onTabSelect(1)

      partners = [test.moh, test.who]
      fetchPartners.resolve(partners)

      expect($scope.partners).toEqual(partners)

      $scope.onTabSelect(2)

      labels = [test.tea, test.coffee]
      fetchLabels.resolve(labels)

      expect($scope.labels).toEqual(labels)

      $scope.onTabSelect(3)

      users = [{id: 101, name: "Tom McTicket", replies: {last_month: 5, this_month: 10, total: 20}}]
      fetchUsers.resolve(users)

      expect($scope.users).toEqual(users)
    )
  )

  #=======================================================================
  # Tests for LabelController
  #=======================================================================
  describe('LabelController', () ->
    LabelService = null
    $scope = null

    beforeEach(inject((_LabelService_) ->
      LabelService = _LabelService_

      $scope = $rootScope.$new()
      $window.contextData = {label: test.tea}
      $controller('LabelController', {$scope: $scope})
    ))

    it('onDeleteLabel', () ->
      confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
      deleteLabel = spyOnPromise($q, $scope, LabelService, 'delete')
      spyOn(UtilsService, 'navigate')

      $scope.onDeleteLabel()

      confirmModal.resolve()
      deleteLabel.resolve()

      expect(LabelService.delete).toHaveBeenCalledWith(test.tea)
      expect(UtilsService.navigate).toHaveBeenCalledWith('/org/home/#/labels')
    )
  )

  #=======================================================================
  # Tests for PartnerController
  #=======================================================================
  describe('PartnerController', () ->
    PartnerService = null
    StatisticsService = null
    UserService = null
    $location = null
    $scope = null

    beforeEach(inject((_PartnerService_, _StatisticsService_, _UserService_, _$location_) ->
      PartnerService = _PartnerService_
      StatisticsService = _StatisticsService_
      UserService = _UserService_
      $location = _$location_

      $scope = $rootScope.$new()
      $window.contextData = {partner: test.moh}
      $controller('PartnerController', {$scope: $scope})
    ))

    it('onTabSelect', () ->
      expect($scope.users).toEqual([])
      expect($scope.initialisedTabs).toEqual([])

      fetchUsers = spyOnPromise($q, $scope, UserService, 'fetchInPartner')
      repliesChart = spyOnPromise($q, $scope, StatisticsService, 'repliesChart')

      $scope.onTabSelect(0)

      expect(StatisticsService.repliesChart).toHaveBeenCalledWith(test.moh, null)
      expect($scope.initialisedTabs).toEqual([0])
      expect($location.path()).toEqual('/summary')

      $scope.onTabSelect(2)

      users = [{id: 101, name: "Tom McTicket", replies: {last_month: 5, this_month: 10, total: 20}}]
      fetchUsers.resolve(users)

      expect($scope.users).toEqual(users)
      expect($scope.initialisedTabs).toEqual([0, 2])
      expect($location.path()).toEqual('/users')

      # select the users tab again
      $scope.onTabSelect(2)

      # users shouldn't be re-fetched
      expect(UserService.fetchInPartner.calls.count()).toEqual(1)
      expect($scope.initialisedTabs).toEqual([0, 2])
      expect($location.path()).toEqual('/users')
    )

    it('onDeletePartner', () ->
      confirmModal = spyOnPromise($q, $scope, UtilsService, 'confirmModal')
      deletePartner = spyOnPromise($q, $scope, PartnerService, 'delete')
      spyOn(UtilsService, 'navigate')

      $scope.onDeletePartner()

      confirmModal.resolve()
      deletePartner.resolve()

      expect(PartnerService.delete).toHaveBeenCalledWith(test.moh)
      expect(UtilsService.navigate).toHaveBeenCalledWith('/org/home/#/partners')
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


  describe('PodController', () ->
    $scope = null
    PodUIService = null
    PodApiService = null
    class PodApiServiceError

    bindController = (deps) ->
      $controller('PodController', angular.extend({}, deps, {
        $scope,
        PodApiService,
        PodUIService
      }))

    beforeEach(() ->
      $scope = $rootScope.$new()

      $scope.podId = 21
      $scope.caseId = 23
      $scope.podConfig = {title: 'Foo'}

      $scope.podData = {
        items: [],
        actions: []
      }

      PodUIService = new class PodUIService
        confirmAction: -> $q.resolve()
        alertActionFailure: () -> null
        alertActionApiFailure: () -> null
        alertLoadApiFailure: () -> null

      PodApiService = new class PodApiService
        PodApiServiceError: PodApiServiceError,

        get: -> $q.resolve({
          items: [],
          actions: []
        })

        trigger: -> $q.resolve({success: true})
    )

    describe('init', () ->
      it('should fetch and attach pod data to the scope', () ->
        spyOn(PodApiService, 'get').and.returnValue($q.resolve({
          items: [{
            name: 'Foo',
            value: 'Bar'
          }]
          actions: [{
            type: 'baz',
            name: 'Baz',
            payload: {}
          }]
        }))

        bindController()

        $scope.init(21, 23, {title: 'Baz'})
        $scope.$apply()

        expect($scope.podId).toEqual(21)
        expect($scope.caseId).toEqual(23)
        expect($scope.podConfig).toEqual({title: 'Baz'})
        expect(PodApiService.get).toHaveBeenCalledWith(21, 23)

        expect($scope.podData).toEqual({
          items: [{
            name: 'Foo',
            value: 'Bar'
          }],
          actions: [
            jasmine.objectContaining({
              type: 'baz'
              name: 'Baz',
              payload: {}
            })
          ]
        })
      )

      it("should set the pod status to loading while it is loading", () ->
        d = $q.defer()

        spyOn(PodApiService, 'get').and.returnValue(d.promise.then(-> $q.resolve({
          items: []
          actions: []
        })))

        bindController()

        $scope.init(21, 23, {title: 'Baz'})
        expect($scope.status).toEqual('loading')

        d.resolve()
        $scope.$apply()

        expect($scope.status).toEqual('idle')
      )

      it("should set the pod status to loading_failed if loading fails", () ->
        spyOn(PodApiService, 'get').and.returnValue($q.reject(new PodApiServiceError(null)))

        bindController()

        $scope.init(21, 23, {title: 'Baz'})
        $scope.$apply()
        expect($scope.status).toEqual('loading_failed')
      )
    )

    describe('update', () ->
      it('should fetch and update pod data', () ->
        $scope.podId = 21
        $scope.caseId = 23

        spyOn(PodApiService, 'get').and.returnValue($q.resolve({
          items: [{
            name: 'Foo',
            value: 'Bar'
          }]
          actions: [{
            type: 'baz',
            name: 'Baz',
            payload: {}
          }]
        }))

        bindController()

        $scope.update()
        $scope.$apply()

        expect(PodApiService.get).toHaveBeenCalledWith(21, 23)

        expect($scope.podData).toEqual({
          items: [{
            name: 'Foo',
            value: 'Bar'
          }],
          actions: [
            jasmine.objectContaining({
              type: 'baz'
              name: 'Baz',
              payload: {}
            })
          ]
        })
      )

      it("should default an action's busy text to the action's name", () ->
        $scope.podId = 21
        $scope.caseId = 23

        spyOn(PodApiService, 'get').and.returnValue($q.resolve({
          items: [{
            name: 'Foo',
            value: 'Bar'
          }]
          actions: [{
            type: 'baz',
            name: 'Baz',
            busy_text: 'Bazzing',
            payload: {}
          }, {
            type: 'quux',
            name: 'Quux',
            payload: {}
          }]
        }))

        bindController()

        $scope.update()
        $scope.$apply()

        expect(PodApiService.get).toHaveBeenCalledWith(21, 23)

        expect($scope.podData.actions).toEqual([
          jasmine.objectContaining({
            type: 'baz'
            busyText: 'Bazzing'
          }),
          jasmine.objectContaining({
            type: 'quux',
            busyText: 'Quux'
          })
        ])
      )
    )

    describe('trigger', () ->
      it('should trigger the given action', () ->
        $scope.podId = 21
        $scope.caseId = 23

        bindController()

        spyOn(PodApiService, 'trigger').and.returnValue($q.resolve({
          success: true
        }))

        $scope.trigger({
          type: 'grault',
          payload: {garply: 'waldo'}
        })

        $scope.$apply()

        expect(PodApiService.trigger)
          .toHaveBeenCalledWith(21, 23, 'grault', {garply: 'waldo'})
      )

      it('should mark the action as busy', () ->
        $scope.podData.actions = [{
          type: 'grault'
          isBusy: false,
          payload: {}
        }, {
          type: 'fred',
          isBusy: false,
          payload: {}
        }]

        bindController()

        # defer getting new data indefinitely to prevent isBusy being set to
        # false when we retrieve new data
        spyOn(PodApiService, 'get').and.returnValue($q.defer().promise)

        spyOn(PodApiService, 'trigger').and.returnValue($q.resolve({success: true}))

        $scope.trigger({
          type: 'grault',
          payload: {garply: 'waldo'}
        })

        $scope.$apply()

        expect($scope.podData.actions[0].isBusy).toBe(true)
      )

      it('should mark the action as not busy after api failure', () ->
        $scope.podData.actions = [{
          type: 'grault'
          isBusy: false,
          payload: {}
        }, {
          type: 'fred',
          isBusy: false,
          payload: {}
        }]

        bindController()

        spyOn(PodApiService, 'get')
          .and.returnValue($q.reject(new PodApiServiceError(null)))

        $scope.trigger({
          type: 'grault',
          payload: {garply: 'waldo'}
        })

        $scope.$apply()

        expect($scope.podData.actions[0].isBusy).toBe(false)
      )

      it('should emit an alert event if unsuccessful', (done) ->
        bindController()

        spyOn(PodApiService, 'trigger').and.returnValue($q.resolve({
          success: false,
          payload: {message: 'Foo'}
        }))

        spyOn(PodUIService, 'alertActionFailure').and.returnValue('fakeResult')

        $scope.trigger({
          type: 'grault',
          payload: {garply: 'waldo'}
        })

        $scope.$on('alert', (e, res) ->
          expect(res).toEqual('fakeResult')

          expect(PodUIService.alertActionFailure.calls.allArgs())
            .toEqual([['Foo']])

          done())

        $scope.$apply()
      )

      it('should emit a timelineChanged event if successful', (done) ->
        bindController()
        spyOn(PodApiService, 'trigger').and.returnValue($q.resolve({success: true}))

        $scope.trigger('grault', {garply: 'waldo'})

        $scope.$on('timelineChanged', -> done())

        $scope.$apply()
      )

      it('should emit an alert if trigger api method fails', (done) ->
        bindController()

        spyOn(PodApiService, 'trigger')
          .and.returnValue($q.reject(new PodApiServiceError(null)))

        spyOn(PodUIService, 'alertActionApiFailure')
          .and.returnValue('fakeResult')

        $scope.trigger({
          type: 'grault',
          payload: {garply: 'waldo'}
        })

        $scope.$on('alert', (e, res) ->
          expect(res).toEqual('fakeResult')
          done())

        $scope.$apply()
      )

      it('should emit an alert if get api method fails', (done) ->
        bindController()

        spyOn(PodApiService, 'get')
          .and.returnValue($q.reject(new PodApiServiceError(null)))

        spyOn(PodUIService, 'alertActionApiFailure')
          .and.returnValue('fakeResult')

        $scope.trigger({
          type: 'grault',
          payload: {garply: 'waldo'}
        })

        $scope.$on('alert', (e, res) ->
          expect(res).toEqual('fakeResult')
          done())

        $scope.$apply()
      )

      it('should fetch and attach data to the scope if successful', () ->
        bindController()

        spyOn(PodApiService, 'get').and.returnValue($q.resolve({
          items: [{
            name: 'Foo',
            value: 'Bar'
          }]
          actions: [{
            type: 'baz',
            name: 'Baz',
            payload: {}
          }]
        }))

        spyOn(PodApiService, 'trigger').and.returnValue($q.resolve({success: true}))

        $scope.trigger({
          type: 'grault',
          payload: {garply: 'waldo'}
        })

        $scope.$apply()

        expect($scope.podData).toEqual({
          items: [{
            name: 'Foo',
            value: 'Bar'
          }],
          actions: [
            jasmine.objectContaining({
              type: 'baz'
              name: 'Baz',
              payload: {}
            })
          ]
        })
      )

      it('should show a confirmation model if the action requires it', () ->
        bindController()
        spyOn(PodUIService, 'confirmAction')

        $scope.trigger({
          type: 'grault',
          name: 'Grault',
          confirm: true,
          payload: {garply: 'waldo'}
        })

        $scope.$apply()
        expect(PodUIService.confirmAction.calls.allArgs()).toEqual([['Grault']])
      )
    )

    #=======================================================================
    # Tests for MessageBoardController
    #=======================================================================
    describe('MessageBoardController', () ->
      MessageBoardService = null
      $scope = null

      beforeEach(() ->
        inject((_MessageBoardService_) ->
          MessageBoardService = _MessageBoardService_
        )

        $scope = $rootScope.$new()
        $controller('MessageBoardController', {$scope: $scope})

        # extra test data
        test.comment1 = {id: 101, comment: "Hello 1", user: {id: 201, name: "Joe"}, submitted_on: utcdate(2016, 8, 1, 10, 0), pinned_on: null}
        test.comment2 = {id: 102, comment: "Hello 2", user: {id: 202, name: "Sam"}, submitted_on: utcdate(2016, 8, 1, 11, 0), pinned_on: null}
      )

      it('should initialize correctly', () ->

        fetchComments = spyOnPromise($q, $scope, MessageBoardService, 'fetchComments')
        fetchPinnedComments = spyOnPromise($q, $scope, MessageBoardService, 'fetchPinnedComments')

        $scope.init()
        fetchComments.resolve({results: [test.comment1, test.comment2]})
        fetchPinnedComments.resolve({results: [test.comment2]})

        expect($scope.comments).toEqual([test.comment1, test.comment2])
        expect($scope.pinnedComments).toEqual([test.comment2])
      )

      it('should pin comments', () ->

        pinComment = spyOnPromise($q, $scope, MessageBoardService, 'pinComment')
        fetchComments = spyOnPromise($q, $scope, MessageBoardService, 'fetchComments')
        fetchPinnedComments = spyOnPromise($q, $scope, MessageBoardService, 'fetchPinnedComments')

        $scope.onPin(test.comment1)
        pinComment.resolve()

        fetchComments.resolve({results: [test.comment1, test.comment2]})
        fetchPinnedComments.resolve({results: [test.comment1]})

        expect(MessageBoardService.pinComment).toHaveBeenCalledWith(test.comment1)
      )

      it('should unpin comments', () ->

        unpinComment = spyOnPromise($q, $scope, MessageBoardService, 'unpinComment')
        fetchComments = spyOnPromise($q, $scope, MessageBoardService, 'fetchComments')
        fetchPinnedComments = spyOnPromise($q, $scope, MessageBoardService, 'fetchPinnedComments')

        $scope.onUnpin(test.comment1)
        unpinComment.resolve()

        fetchComments.resolve({results: [test.comment1, test.comment2]})
        fetchPinnedComments.resolve({results: []})

        expect(MessageBoardService.unpinComment).toHaveBeenCalledWith(test.comment1)
      )
    )
  )
)
