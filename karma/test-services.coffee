# Unit tests for our Angular services (services listed A-Z)

describe('services:', () ->
  $httpBackend = null
  $window = null
  $rootScope = null
  test = null

  beforeEach(() ->
    module('templates')
    module('cases')

    inject((_$httpBackend_, _$window_, _$rootScope_) ->
      $httpBackend = _$httpBackend_
      $window = _$window_
      $rootScope = _$rootScope_
    )

    test = {
      # users
      user1: {id: 101, name: "Tom McTest"},

      # labels
      tea: {id: 201, name: "Tea"},
      coffee: {id: 202, name: "Coffee"},

      # partners
      moh: {id: 301, name: "MOH"},
      who: {id: 302, name: "WHO"},

      # contacts
      ann: {id: 401, name: "Ann"},
      bob: {id: 402, name: "Bob"}

      # faqs
      pregnant: {id: 701, name: "Pregnant"},

      # language
      language1: {code: "eng", name: "English"},
      language2: {code: "afr", name: "Afrikaans"},

      # FAQs
      faq1: {id: 501, question: "Am I pregnant?", answer: "yes", language: {code: "eng", name: "English"}, labels: [{id: 201, name: "Tea"}, {id: 202, name: "Coffee"}], parent: null},

      # translation
      translation1: {id: 601, question: "Is ek swanger", answer: "ja", language: {code: "afr", name: "Afrikaans"}, labels: {id: 201, name: "Tea"}, parent: 401},
    }
  )

  #=======================================================================
  # Tests for CaseService
  #=======================================================================
  describe('CaseService', () ->
    CaseService = null

    beforeEach(inject((_CaseService_) ->
      CaseService = _CaseService_

      test.case1 = {
        id: 501,
        summary: "Got tea?",
        labels: [test.tea],
        assignee: test.moh,
        opened_on: utcdate(2016, 5, 27, 11, 0, 0, 0),
        is_closed: false
      }
    ))

    describe('addNote', () ->
      it('posts to note endpoint', () ->
        $httpBackend.expectPOST('/case/note/501/', {note: "Hello there"}).respond('')
        CaseService.addNote(test.case1, "Hello there").then(() ->
          expect(test.case1.watching).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('fetchOld', () ->
      it('gets cases from search endpoint', () ->
        $httpBackend.expectGET('/case/search/?folder=open').respond('{"results":[{"id":501,"opened_on":"2016-05-17T08:49:13.698864"}],"has_more":true}')
        CaseService.fetchOld({folder: "open"}).then((data) ->
          expect(data.results).toEqual([{id: 501, opened_on: utcdate(2016, 5, 17, 8, 49, 13, 698)}])
          expect(data.hasMore).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('fetchTimeline', () ->
      it('gets cases from timeline endpoint', () ->
        $httpBackend.expectGET('/case/timeline/501/?after=2016-05-28T09:00:00.000Z').respond('{"results":[{"time":"2016-05-17T08:49:13.698864","type":"A","item":{}}]}')
        CaseService.fetchTimeline(test.case1, utcdate(2016, 5, 28, 9, 0, 0, 0)).then((data) ->
          expect(data.results).toEqual([{
            time: utcdate(2016, 5, 17, 8, 49, 13, 698),
            type: 'A',
            item: {}
          }])
        )
        $httpBackend.flush()
      )
    )

    describe('fetchSingle', () ->
      it('gets case from fetch endpoint', () ->
        $httpBackend.expectGET('/case/fetch/501/').respond('{"id":501,"opened_on":"2016-05-17T08:49:13.698864"}')
        CaseService.fetchSingle(501).then((caseObj) ->
          expect(caseObj).toEqual({id: 501, opened_on: utcdate(2016, 5, 17, 8, 49, 13, 698)})
        )
        $httpBackend.flush()
      )
    )

    describe('reassign', () ->
      it('posts to reassign endpoint', () ->
        $httpBackend.expectPOST(
          '/case/reassign/501/', {assignee: test.who.id, user_assignee: test.user1.id}).respond('')
        CaseService.reassign(test.case1, test.who, test.user1).then(() ->
          expect(test.case1.assignee).toEqual(test.who)
        )
        $httpBackend.flush()
      )
    )

    describe('close', () ->
      it('posts to close endpoint and closes case', () ->
        $httpBackend.expectPOST('/case/close/501/', {note: "Hello there"}).respond('')
        CaseService.close(test.case1, "Hello there").then(() ->
          expect(test.case1.is_closed).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('open', () ->
      it('posts to open endpoint', () ->
        $httpBackend.expectPOST('/case/open/', {message: 401, summary: "Hi", assignee: 301, user_assignee: test.user1.id}).respond('{"id": 501, "is_new": true, "watching": true}')
        CaseService.open({id: 401, text: "Hi"}, "Hi", test.moh, test.user1).then((caseObj) ->
          expect(caseObj.id).toEqual(501)
          expect(caseObj.is_new).toEqual(true)
          expect(caseObj.watching).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('relabel', () ->
      it('posts to label endpoint', () ->
        $httpBackend.expectPOST('/case/label/501/', {labels: [202]}).respond('')
        CaseService.relabel(test.case1, [test.coffee]).then(() ->
          expect(test.case1.labels).toEqual([test.coffee])
        )
        $httpBackend.flush()
      )
    )

    describe('reopen', () ->
      it('posts to reopen endpoint and reopens case', () ->
        test.case1.is_closed = true

        $httpBackend.expectPOST('/case/reopen/501/', {note: "Hello there"}).respond('')
        CaseService.reopen(test.case1, "Hello there").then(() ->
          expect(test.case1.is_closed).toEqual(false)
          expect(test.case1.watching).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('replyTo', () ->
      it('posts to reply endpoint', () ->
        $httpBackend.expectPOST('/case/reply/501/', {text: "Hello there"}).respond('')
        CaseService.replyTo(test.case1, "Hello there").then(() ->
          expect(test.case1.watching).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('startExport', () ->
      it('posts to export endpoint', () ->
        $httpBackend.expectPOST('/caseexport/create/?folder=open', null).respond('')
        CaseService.startExport({folder: "open"})
        $httpBackend.flush()
      )
    )

    describe('updateSummary', () ->
      it('posts to update summary endpoint', () ->
        $httpBackend.expectPOST('/case/update_summary/501/', {summary: "Got coffee?"}).respond('')
        CaseService.updateSummary(test.case1, "Got coffee?").then(() ->
          expect(test.case1.summary).toEqual("Got coffee?")
        )
        $httpBackend.flush()
      )
    )

    describe('watch', () ->
      it('posts to watch endpoint', () ->
        $httpBackend.expectPOST('/case/watch/501/', null).respond('')
        CaseService.watch(test.case1).then(() ->
          expect(test.case1.watching).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('unwatch', () ->
      it('posts to unwatch endpoint', () ->
        $httpBackend.expectPOST('/case/unwatch/501/', null).respond('')
        CaseService.unwatch(test.case1).then(() ->
          expect(test.case1.watching).toEqual(false)
        )
        $httpBackend.flush()
      )
    )
  )

  #=======================================================================
  # Tests for ContactService
  #=======================================================================
  describe('ContactService', () ->
    ContactService = null

    beforeEach(inject((_ContactService_) ->
      ContactService = _ContactService_
    ))

    describe('fetch', () ->
      it('gets contact from fetch endpoint', () ->
        $httpBackend.expectGET('/contact/fetch/401/').respond('{"id":401, "name":"Ann", "fields":{}, "urns": []}')
        ContactService.fetch(401).then((contact) ->
          expect(contact).toEqual({id: 401, name: "Ann", fields:{}, urns:[]})
        )
        $httpBackend.flush()
      )
    )

    describe('fetchCases', () ->
      it('gets contacts cases from fetch endpoint', () ->
        $httpBackend.expectGET('/contact/cases/401/').respond('{"results":[{"id": 501, "opened_on": "2016-05-17T08:49:13.698864"}]}')
        ContactService.fetchCases(test.ann).then((cases) ->
          expect(cases).toEqual([{id: 501, opened_on: utcdate(2016, 5, 17, 8, 49, 13, 698)}])
        )
        $httpBackend.flush()
      )
    )
  )

  #=======================================================================
  # Tests for LabelService
  #=======================================================================
  describe('LabelService', () ->
    LabelService = null

    beforeEach(inject((_LabelService_) ->
      LabelService = _LabelService_
    ))

    describe('delete', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/label/delete/201/', null).respond("")
        LabelService.delete(test.tea)
        $httpBackend.flush()
      )
    )
  )

  #=======================================================================
  # Tests for MessageService
  #=======================================================================
  describe('MessageService', () ->
    MessageService = null

    beforeEach(inject((_MessageService_) ->
      MessageService = _MessageService_

      test.msg1 = {id: 101, text: "Hello 1", labels: [test.tea], flagged: true, archived: false}
      test.msg2 = {id: 102, text: "Hello 2", labels: [test.coffee], flagged: false, archived: false}
    ))

    describe('fetchHistory', () ->
      it('gets actions from history endpoint', () ->
        $httpBackend.expectGET('/message/history/101/').respond('{"actions":[{"action":"archive","created_on":"2016-05-17T08:49:13.698864"}]}')
        MessageService.fetchHistory(test.msg1).then((actions) ->
          expect(actions).toEqual([{action: "archive", "created_on": utcdate(2016, 5, 17, 8, 49, 13, 698)}])
        )
        $httpBackend.flush()
      )
    )

    describe('fetchOld', () ->
      it('gets messages from search endpoint', () ->
        $httpBackend.expectGET('/message/search/?archived=0&folder=inbox').respond('{"results":[{"id":501,"time":"2016-05-17T08:49:13.698864"}],"has_more":true}')
        MessageService.fetchOld({folder: "inbox"}).then((data) ->
          expect(data.results).toEqual([{id: 501, time: utcdate(2016, 5, 17, 8, 49, 13, 698)}])
          expect(data.hasMore).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('bulkArchive', () ->
      it('posts to bulk action endpoint', () ->
        $httpBackend.expectPOST('/message/action/archive/', {messages: [101, 102]}).respond('')
        MessageService.bulkArchive([test.msg1, test.msg2]).then(() ->
          expect(test.msg1.archived).toEqual(true)
          expect(test.msg2.archived).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('bulkFlag', () ->
      it('posts to bulk action endpoint', () ->
        $httpBackend.expectPOST('/message/action/flag/', {messages: [101, 102]}).respond('')
        MessageService.bulkFlag([test.msg1, test.msg2], true).then(() ->
          expect(test.msg1.flagged).toEqual(true)
          expect(test.msg2.flagged).toEqual(true)
        )
        $httpBackend.flush()

        $httpBackend.expectPOST('/message/action/unflag/', {messages: [101, 102]}).respond('')
        MessageService.bulkFlag([test.msg1, test.msg2], false).then(() ->
          expect(test.msg1.flagged).toEqual(false)
          expect(test.msg2.flagged).toEqual(false)
        )
        $httpBackend.flush()
      )
    )

    describe('bulkLabel', () ->
      it('posts to bulk action endpoint', () ->
        $httpBackend.expectPOST('/message/action/label/', {messages: [101, 102], label: 201}).respond('')
        MessageService.bulkLabel([test.msg1, test.msg2], test.tea).then(() ->
          expect(test.msg1.labels).toEqual([test.tea])
          expect(test.msg2.labels).toEqual([test.coffee, test.tea])
        )
        $httpBackend.flush()
      )
    )

    describe('bulkReply', () ->
      it('posts to bulk reply endpoint', () ->
        $httpBackend.expectPOST('/message/bulk_reply/', {messages: [101, 102], text: "Welcome"}).respond('')
        MessageService.bulkReply([test.msg1, test.msg2], "Welcome")
        $httpBackend.flush()
      )
    )

    describe('bulkRestore', () ->
      it('posts to bulk action endpoint', () ->
        $httpBackend.expectPOST('/message/action/restore/', {messages: [101, 102]}).respond('')
        MessageService.bulkRestore([test.msg1, test.msg2]).then(() ->
          expect(test.msg1.archived).toEqual(false)
          expect(test.msg2.archived).toEqual(false)
        )
        $httpBackend.flush()
      )
    )

    describe('forward', () ->
      it('posts to forward endpoint', () ->
        $httpBackend.expectPOST('/message/forward/101/', {text: "Welcome", urns: ["tel:+260964153686"]}).respond('')
        MessageService.forward(test.msg1, "Welcome", {urn: "tel:+260964153686"})
        $httpBackend.flush()
      )
    )

    describe('relabel', () ->
      it('posts to label endpoint', () ->
        $httpBackend.expectPOST('/message/label/101/', {labels: [202]}).respond('')
        MessageService.relabel(test.msg1, [test.coffee]).then(() ->
          expect(test.msg1.labels).toEqual([test.coffee])
        )
        $httpBackend.flush()
      )
    )

    describe('startExport', () ->
      it('posts to export endpoint', () ->
        $httpBackend.expectPOST('/messageexport/create/?archived=0&folder=inbox', null).respond('')
        MessageService.startExport({folder: "inbox"})
        $httpBackend.flush()
      )
    )

    describe('checkLock', () ->
      it('posts to lock check endpoint', () ->
        $httpBackend.expectPOST('/message/lock/lock/', {messages: [101, 102]}).respond('{"messages": [101, 102]}')
        MessageService.checkLock([test.msg1, test.msg2]).then((data) ->
          expect(data.items).toEqual([101, 102])
        )
        $httpBackend.flush()
      )
    )
  )

  #=======================================================================
  # Tests for FaqService
  #=======================================================================
  describe('FaqService', () ->
    FaqService = null

    beforeEach(inject((_FaqService_) ->
      FaqService = _FaqService_
    ))

    describe('fetchFaqs', () ->
      it('gets FAQs from search endpoint', () ->
        $httpBackend.expectGET('/faq/search/?label=201')
        .respond('{
          "results": [{
            "id": 702,
            "question": "example question 1",
            "answer": "example answer 1",
            "labels": [201]
          }],
          "has_more": false
        }')
        FaqService.fetchFaqs({label: {id: 201}}).then((replies) ->
          expect(replies).toEqual([{
            id: 702,
            question: "example question 1",
            answer: "example answer 1",
            labels: [201]
          }])
        )
        $httpBackend.flush()
      )

      it('gets FAQs from search endpoint with multiple filters', () ->
        $httpBackend.expectGET('/faq/search/?label=201&text=example')
        .respond('{
          "results": [{
            "id": 702,
            "question": "example question 1",
            "answer": "example answer 1",
            "labels": [201]
          }],
          "has_more": false
        }')
        FaqService.fetchFaqs({label: {id: 201}, text: "example"}).then((replies) ->
          expect(replies).toEqual([{
            id: 702,
            question: "example question 1",
            answer: "example answer 1",
            labels: [201]
          }])
        )
        $httpBackend.flush()
      )
    )

    describe('fetchAllFaqs', () ->
      it('gets FAQs for use in translations', () ->
        $httpBackend.expectGET('/faq/search/?')
        .respond('{
          "results": [{
            "id": 401,
            "question": "Am I pregnant?",
            "answer": "yes",
            "labels": [201, 202],
            "language": [{"code": "eng", "name": "English"}],
            "parent": null
          }]
        }')
        FaqService.fetchAllFaqs().then((results) ->
          expect(results).toEqual([{
            id: 401,
            question: "Am I pregnant?",
            answer: "yes",
            labels: [201, 202],
            language: [{code: "eng", name: "English"}],
            parent: null
          }])
        )
        $httpBackend.flush()
      )
    )

    describe('createFaq', () ->
      it('posts to FAQ create endpoint', () ->
        $httpBackend.expectPOST('/faq/create/', test.faq1).respond('')
        FaqService.createFaq(test.faq1)
        $httpBackend.flush()
      )
    )

    describe('updateFaq', () ->
      it('posts to FAQ update endpoint', () ->
        $httpBackend.expectPOST('/faq/update/501/', test.faq1).respond('')
        FaqService.updateFaq(test.faq1)
        $httpBackend.flush()
      )
    )

    describe('delete', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/faq/delete/501/', null).respond("")
        FaqService.delete(test.faq1)
        $httpBackend.flush()
      )
    )

    describe('deleteTranslation', () ->
      it('posts to delete translation endpoint', () ->
        $httpBackend.expectPOST('/faq/delete/601/', null).respond("")
        FaqService.deleteTranslation(test.translation1)
        $httpBackend.flush()
      )
    )

    describe('fetchLanguages', () ->
      it('gets available languages', () ->
        $httpBackend.expectGET('/faq/languages/')
        .respond('{
          "results": [{"code": "eng", "name": "English"}],
          "iso_list": [{"iso639_2_b": "eng", "name": "English"}]
        }')
        FaqService.fetchLanguages().then((results) ->
          expect(results).toEqual([{code: "eng", name: "English"}])
        )
        $httpBackend.flush()
      )
    )

    describe('fetchAllLanguages', () ->
      it('gets all languages from iso639', () ->
        $httpBackend.expectGET('/faq/languages/')
        .respond('{
          "results": [{"code": "eng", "name": "English"}],
          "iso_list": [{"iso639_2_b": "eng", "name": "English"}]
        }')
        FaqService.fetchAllLanguages().then((iso_list) ->
          expect(iso_list).toEqual([{iso639_2_b: "eng", name: "English"}])
        )
        $httpBackend.flush()
      )
    )

  )

  #=======================================================================
  # Tests for OutgoingService
  #=======================================================================
  describe('OutgoingService', () ->
    OutgoingService = null

    beforeEach(inject((_OutgoingService_) ->
      OutgoingService = _OutgoingService_
    ))

    describe('fetchOld', () ->
      it('gets messages from search endpoint', () ->
        $httpBackend.expectGET('/outgoing/search/?folder=sent').respond('{"results":[{"id":501,"time":"2016-05-17T08:49:13.698864"}],"has_more":true}')
        OutgoingService.fetchOld({folder: "sent"}).then((data) ->
          expect(data.results).toEqual([{id: 501, time: utcdate(2016, 5, 17, 8, 49, 13, 698)}])
          expect(data.hasMore).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('fetchReplies', () ->
      it('gets messages from replies endpoint', () ->
        $httpBackend.expectGET('/outgoing/search_replies/?partner=301').respond('{"results":[{"id":501,"time":"2016-05-17T08:49:13.698864"}],"has_more":true}')
        OutgoingService.fetchReplies({partner: test.moh}).then((data) ->
          expect(data.results).toEqual([{id: 501, time: utcdate(2016, 5, 17, 8, 49, 13, 698)}])
          expect(data.hasMore).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('startReplyExport', () ->
      it('posts to export endpoint', () ->
        $httpBackend.expectPOST('/replyexport/create/?partner=301', null).respond('')
        OutgoingService.startReplyExport({partner: test.moh})
        $httpBackend.flush()
      )
    )
  )

  #=======================================================================
  # Tests for PartnerService
  #=======================================================================
  describe('PartnerService', () ->
    PartnerService = null

    beforeEach(inject((_PartnerService_) ->
      PartnerService = _PartnerService_
    ))

    describe('delete', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/partner/delete/301/', null).respond('')
        PartnerService.delete(test.moh)
        $httpBackend.flush()
      )
    )
  )

  #=======================================================================
  # Tests for StatisticsService
  #=======================================================================
  describe('StatisticsService', () ->
    StatisticsService = null

    beforeEach(inject((_StatisticsService_) ->
      StatisticsService = _StatisticsService_
    ))

    describe('repliesChart', () ->
      it('fetches from replies chart endpoint', () ->
        $httpBackend.expectGET('/stats/replies_chart/?partner=301').respond('{"categories":["Jan", "Feb"], "series":[2, 3]}')
        StatisticsService.repliesChart(test.moh).then((data) ->
          expect(data).toEqual({categories: ["Jan", "Feb"], series: [2, 3]})
        )
        $httpBackend.flush()
      )
    )
  )

  #=======================================================================
  # Tests for UserService
  #=======================================================================
  describe('UserService', () ->
    UserService = null

    beforeEach(inject((_UserService_) ->
      UserService = _UserService_
    ))

    describe('fetchInPartner', () ->
      it('fetches from users endpoint', () ->
        $httpBackend.expectGET('/user/?partner=301&with_activity=false').respond('{"results":[{"id": 101, "name": "Tom McTest", "replies": {}}]}')
        UserService.fetchInPartner(test.moh).then((users) ->
          expect(users).toEqual([{id: 101, name: "Tom McTest", replies: {}}])
        )
        $httpBackend.flush()
      )
    )

    describe('fetchNonPartner', () ->
      it('fetches from users endpoint', () ->
        $httpBackend.expectGET('/user/?non_partner=true&with_activity=true').respond('{"results":[{"id": 101, "name": "Tom McTest", "replies": {}}]}')
        UserService.fetchNonPartner(true).then((users) ->
          expect(users).toEqual([{id: 101, name: "Tom McTest", replies: {}}])
        )
        $httpBackend.flush()
      )
    )

    describe('delete', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/user/delete/101/', null).respond('')
        UserService.delete(test.user1)
        $httpBackend.flush()
      )
    )
  )

  #=======================================================================
  # Tests for UtilsService
  #=======================================================================
  describe('UtilsService', () ->
    UtilsService = null
    $uibModal = null

    beforeEach(() ->
      inject((_UtilsService_, _$uibModal_) ->
        UtilsService = _UtilsService_
        $uibModal = _$uibModal_
      )

      spyOn($uibModal, 'open').and.callThrough()
    )

    describe('displayAlert', () ->
      it('called external displayAlert', () ->
        $window.displayAlert = jasmine.createSpy('$window.displayAlert')

        UtilsService.displayAlert('error', "Uh Oh!")

        expect($window.displayAlert).toHaveBeenCalledWith('error', "Uh Oh!")
      )
    )

    describe('navigate', () ->
      it('changes location of $window', () ->
        spyOn($window.location, 'replace')

        UtilsService.navigate("http://example.com")

        expect($window.location.replace).toHaveBeenCalledWith("http://example.com")
      )
    )

    describe('navigateBack', () ->
      it('calls history.back', () ->
        spyOn($window.history, 'back')

        UtilsService.navigateBack()

        expect($window.history.back).toHaveBeenCalled()
      )
    )

    describe('confirmModal', () ->
      it('opens confirm modal', () ->
        UtilsService.confirmModal("OK?")

        modalOptions = $uibModal.open.calls.mostRecent().args[0]
        expect(modalOptions.templateUrl).toEqual('/partials/modal_confirm.html')
        expect(modalOptions.resolve.prompt()).toEqual("OK?")
      )
    )

    describe('editModal', () ->
      it('opens edit modal', () ->
        UtilsService.editModal("Edit", "this...")

        modalOptions = $uibModal.open.calls.mostRecent().args[0]
        expect(modalOptions.templateUrl).toEqual('/partials/modal_edit.html')
        expect(modalOptions.resolve.title()).toEqual("Edit")
        expect(modalOptions.resolve.initial()).toEqual("this...")
      )
    )

    describe('composeModal', () ->
      it('opens compose modal', () ->
        UtilsService.composeModal("Compose", "this...")

        modalOptions = $uibModal.open.calls.mostRecent().args[0]
        expect(modalOptions.templateUrl).toEqual('/partials/modal_compose.html')
        expect(modalOptions.resolve.title()).toEqual("Compose")
        expect(modalOptions.resolve.initial()).toEqual("this...")
      )
    )

    describe('assignModal', () ->
      it('opens assign modal', () ->
        UtilsService.assignModal("Assign", "this...", [test.moh, test.who], [test.user1])

        modalOptions = $uibModal.open.calls.mostRecent().args[0]
        expect(modalOptions.templateUrl).toEqual('/partials/modal_assign.html')
        expect(modalOptions.resolve.title()).toEqual("Assign")
        expect(modalOptions.resolve.prompt()).toEqual("this...")
        expect(modalOptions.resolve.partners()).toEqual([test.moh, test.who])
        expect(modalOptions.resolve.users()).toEqual([test.user1])
      )
    )

    describe('noteModal', () ->
      it('opens note modal', () ->
        UtilsService.noteModal("Note", "this...", 'danger', 100)

        modalOptions = $uibModal.open.calls.mostRecent().args[0]
        expect(modalOptions.templateUrl).toEqual('/partials/modal_note.html')
        expect(modalOptions.resolve.title()).toEqual("Note")
        expect(modalOptions.resolve.prompt()).toEqual("this...")
        expect(modalOptions.resolve.style()).toEqual('danger')
        expect(modalOptions.resolve.maxLength()).toEqual(100)
      )
    )

    describe('labelModal', () ->
      it('opens label modal', () ->
        UtilsService.labelModal("Label", "this...", [test.tea, test.coffee], [test.tea])

        modalOptions = $uibModal.open.calls.mostRecent().args[0]
        expect(modalOptions.templateUrl).toEqual('/partials/modal_label.html')
        expect(modalOptions.resolve.title()).toEqual("Label")
        expect(modalOptions.resolve.prompt()).toEqual("this...")
        expect(modalOptions.resolve.labels()).toEqual([test.tea, test.coffee])
        expect(modalOptions.resolve.initial()).toEqual([test.tea])
      )
    )

    describe('newCaseModal', () ->
      it('opens new case modal', () ->
        UtilsService.newCaseModal("this...", 100, test.ann, [test.moh, test.who])

        modalOptions = $uibModal.open.calls.mostRecent().args[0]
        expect(modalOptions.templateUrl).toEqual('/partials/modal_newcase.html')
        expect(modalOptions.resolve.summaryInitial()).toEqual("this...")
        expect(modalOptions.resolve.summaryMaxLength()).toEqual(100)
        expect(modalOptions.resolve.partners()).toEqual([test.moh, test.who])
      )
    )

    describe('dateRangeModal', () ->
      it('opens date range modal', () ->
        UtilsService.dateRangeModal("Label", "this...")

        modalOptions = $uibModal.open.calls.mostRecent().args[0]
        expect(modalOptions.templateUrl).toEqual('/partials/modal_daterange.html')
        expect(modalOptions.resolve.title()).toEqual("Label")
        expect(modalOptions.resolve.prompt()).toEqual("this...")
      )
    )

    describe('faqModal', () ->
      it('opens FAQ modal', () ->
        UtilsService.faqModal("Title", [test.translation1], [test.faq1], true)

        modalOptions = $uibModal.open.calls.mostRecent().args[0]
        expect(modalOptions.templateUrl).toEqual('/partials/modal_faq.html')
        expect(modalOptions.resolve.title()).toEqual("Title")
        expect(modalOptions.resolve.translation()).toEqual([test.translation1])
        expect(modalOptions.resolve.faq()).toEqual([test.faq1])
        expect(modalOptions.resolve.isFaq()).toEqual(true)
      )
    )

  )

  #=======================================================================
  # Tests for ModalService
  #=======================================================================
  describe('ModalService', () ->
    ModalService = null

    beforeEach(inject((_ModalService_) ->
      ModalService = _ModalService_
    ))

    describe('confirm', () ->
      describe('if no template url is given', () ->
        it('should draw the modal', () ->
          ModalService.confirm({
            title: 'Foo',
            prompt: 'Bar?'
          })

          $rootScope.$apply()

          expect(document.querySelector('.modal-title').textContent)
            .toMatch('Foo')

          expect(document.querySelector('.modal-body').textContent)
            .toMatch('Bar?')
        )

        it('should fulfill if the modal is accepted', () ->
          fulfilled = false

          ModalService.confirm({
            title: 'Foo',
            prompt: 'Bar?'
          })
          .then(-> fulfilled = true)

          $rootScope.$apply()
          expect(fulfilled).toBe(false)

          angular.element(document.querySelector('.btn-modal-accept'))
            .triggerHandler('click')

          $rootScope.$apply()
          expect(fulfilled).toBe(true)
        )

        it('should reject if the modal is cancelled', () ->
          rejected = false

          ModalService.confirm({
            title: 'Foo',
            prompt: 'Bar?'
          })
          .catch(-> rejected = true)

          $rootScope.$apply()
          expect(rejected).toBe(false)

          angular.element(document.querySelector('.btn-modal-cancel'))
            .triggerHandler('click')

          $rootScope.$apply()
          expect(rejected).toBe(true)
        )
      )

      describe('if a template url is given', () ->
        it('should draw the modal', () ->
          ModalService.confirm({
            templateUrl: '/sitestatic/karma/templates/modals/dummy-confirm.html',
            context: {title: 'Foo'}
          })

          $rootScope.$apply()

          expect(document.querySelector('.modal-title').textContent)
            .toMatch('Foo')

          expect(document.querySelector('.modal-body').textContent)
            .toMatch('Are you sure you want to do this?')
        )

        it('should fulfill if the modal is accepted', () ->
          fulfilled = false

          ModalService.confirm({
            templateUrl: '/sitestatic/karma/templates/modals/dummy-confirm.html',
            context: {title: 'Foo'}
          })
          .then(-> fulfilled = true)

          $rootScope.$apply()
          expect(fulfilled).toBe(false)

          angular.element(document.querySelector('.btn-modal-accept'))
            .triggerHandler('click')

          $rootScope.$apply()
          expect(fulfilled).toBe(true)
        )

        it('should reject if the modal is cancelled', () ->
          rejected = false

          ModalService.confirm({
            templateUrl: '/sitestatic/karma/templates/modals/dummy-confirm.html',
            context: {title: 'Foo'}
          })
          .catch(-> rejected = true)

          $rootScope.$apply()
          expect(rejected).toBe(false)

          angular.element(document.querySelector('.btn-modal-cancel'))
            .triggerHandler('click')

          $rootScope.$apply()
          expect(rejected).toBe(true)
        )
      )
    )

    describe('createCase', () ->
        it('should draw the modal', () ->
          $httpBackend.expectGET('/partner/?with_activity=false')
            .respond([])
          ModalService.createCase({
            title: 'Foo',
          })

          $rootScope.$apply()

          expect(document.querySelector('.modal-title').textContent)
            .toMatch('Foo')
        )

        it('should fulfill if the modal is accepted', () ->
          fulfilled = false

          $httpBackend.expectGET('/partner/?with_activity=false')
            .respond([])
          ModalService.createCase({
            title: 'Foo',
          })
          .then(-> fulfilled = true)

          $rootScope.$apply()
          expect(fulfilled).toBe(false)

          angular.element(document.querySelector('input')).val('+27741234567').triggerHandler('change')
          angular.element(document.querySelector('textarea')).val('summary').triggerHandler('change')
          angular.element(document.querySelector('.btn-modal-accept'))
            .triggerHandler('click')

          $rootScope.$apply()
          expect(fulfilled).toBe(true)
        )

        it('should reject if the modal is cancelled', () ->
          rejected = false

          ModalService.confirm({
            title: 'Foo',
          })
          .catch(-> rejected = true)

          $rootScope.$apply()
          expect(rejected).toBe(false)

          angular.element(document.querySelector('.btn-modal-cancel'))
            .triggerHandler('click')

          $rootScope.$apply()
          expect(rejected).toBe(true)
        )

        it('should display an error if there is no urn', () ->
          fulfilled = false

          $httpBackend.expectGET('/partner/?with_activity=false')
            .respond([])
          ModalService.createCase({
            title: 'Foo',
          })
          .then(-> fulfilled = true)

          $rootScope.$apply()
          expect(fulfilled).toBe(false)

          angular.element(document.querySelector('.btn-modal-accept'))
            .triggerHandler('click')

          $rootScope.$apply()

          expect(document.querySelector('.has-error label').innerHTML).toContain('Contact')
          expect(document.querySelector('.form-group .help-block').innerHTML).toContain('Required')
          expect(document.querySelector('.form-group .help-block').className).not.toContain('ng-hide')
          expect(fulfilled).toBe(false)
        )

        it('should display an error if there is an invalid phone urn', () ->
          fulfilled = false

          $httpBackend.expectGET('/partner/?with_activity=false')
            .respond([])
          ModalService.createCase({
            title: 'Foo',
          })
          .then(-> fulfilled = true)

          $rootScope.$apply()
          expect(fulfilled).toBe(false)

          angular.element(document.querySelector('input')).val('0741234567').triggerHandler('change')
          angular.element(document.querySelector('textarea')).val('summary').triggerHandler('change')
          angular.element(document.querySelector('.btn-modal-accept'))
            .triggerHandler('click')

          $rootScope.$apply()

          expect(document.querySelector('.has-error label').innerHTML).toContain('Contact')
          expect(document.querySelectorAll('.form-group .help-block')[1].innerHTML).toContain(
            'Invalid phone number format. Should be in the format +27741234567')
          expect(document.querySelectorAll('.form-group .help-block')[1].className).not.toContain('ng-hide')
          expect(fulfilled).toBe(false)
        )

        it('should not display an error for an invalid phone urn if another urn type is selected', () ->
          fulfilled = false

          $httpBackend.expectGET('/partner/?with_activity=false')
            .respond([])
          ModalService.createCase({
            title: 'Foo',
          })
          .then(-> fulfilled = true)

          $rootScope.$apply()
          expect(fulfilled).toBe(false)

          # Select twitter URN type
          angular.element(document.querySelectorAll('a')[1]).triggerHandler('click')
          # With invalid phone number
          angular.element(document.querySelector('input')).val('0741234567').triggerHandler('change')
          angular.element(document.querySelector('textarea')).val('summary').triggerHandler('change')
          angular.element(document.querySelector('.btn-modal-accept'))
            .triggerHandler('click')

          $rootScope.$apply()

          expect(document.querySelectorAll('.form-group .help-block')[1].className).toContain('ng-hide')
          expect(fulfilled).toBe(true)
        )


        it('should display an error if there is no summary', () ->
          fulfilled = false

          $httpBackend.expectGET('/partner/?with_activity=false')
            .respond([])
          ModalService.createCase({
            title: 'Foo',
          })
          .then(-> fulfilled = true)

          $rootScope.$apply()
          expect(fulfilled).toBe(false)

          angular.element(document.querySelector('input')).val('+27741234567').triggerHandler('change')
          angular.element(document.querySelector('.btn-modal-accept'))
            .triggerHandler('click')

          $rootScope.$apply()

          expect(document.querySelector('.has-error label').innerHTML).toContain('Summary')
          expect(document.querySelectorAll('.form-group')[1].querySelector('.help-block').innerHTML)
              .toContain('Required')
          expect(document.querySelectorAll('.form-group')[1].querySelector('.help-block').className)
              .not.toContain('ng-hide')
          expect(fulfilled).toBe(false)
        )

        it('should display an error if the summary is too long', () ->
          fulfilled = false

          $httpBackend.expectGET('/partner/?with_activity=false')
            .respond([])
          ModalService.createCase({
            title: 'Foo',
            maxLength: 3,
          })
          .then(-> fulfilled = true)

          $rootScope.$apply()
          expect(fulfilled).toBe(false)

          angular.element(document.querySelector('input')).val('+27741234567').triggerHandler('change')
          angular.element(document.querySelector('textarea')).val('too long').triggerHandler('change')
          angular.element(document.querySelector('.btn-modal-accept'))
            .triggerHandler('click')

          $rootScope.$apply()

          expect(document.querySelector('.has-error label').innerHTML).toContain('Summary')
          expect(document.querySelectorAll('.form-group')[1].querySelectorAll('.help-block')[1].innerHTML)
              .toContain('Too long')
          expect(document.querySelectorAll('.form-group')[1].querySelectorAll('.help-block')[1].className)
              .not.toContain('ng-hide')
          expect(fulfilled).toBe(false)
        )
    )
  )
)
