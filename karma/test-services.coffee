# Unit tests for our Angular services (services listed A-Z)

describe('services:', () ->
  $httpBackend = null

  beforeEach(() ->
    module('cases')

    inject((_$httpBackend_) ->
      $httpBackend = _$httpBackend_
    )
  )

  describe('CaseService', () ->
    CaseService = null
    testCase = null

    beforeEach(inject((_CaseService_) ->
      CaseService = _CaseService_

      testCase = {
        id: 501,
        summary: "Got tea?",
        assignee: {id: 201, name: "McTest Partners Ltd"},
        opened_on: utcdate(2016, 5, 27, 11, 0, 0, 0),
        is_closed: false
      }
    ))
    
    describe('addNote', () ->
      it('posts to note endpoint', () ->
        $httpBackend.expectPOST('/case/note/501/', 'note=Hello+there').respond('')
        CaseService.addNote(testCase, "Hello there")
        $httpBackend.flush()
      )
    )

    describe('reassign', () ->
      it('posts to reassign endpoint', () ->
        newAssignee = {id: 202, name: "Helpers"}

        $httpBackend.expectPOST('/case/reassign/501/', 'assignee=202').respond('')
        CaseService.reassign(testCase, newAssignee).then(() ->
          expect(testCase.assignee).toEqual(newAssignee)
        )
        $httpBackend.flush()
      )
    )

    describe('close', () ->
      it('posts to close endpoint and closes case', () ->
        $httpBackend.expectPOST('/case/close/501/', 'note=Hello+there').respond('')
        CaseService.close(testCase, "Hello there").then(() ->
          expect(testCase.is_closed).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('reopen', () ->
      it('posts to reopen endpoint and reopens case', () ->
        testCase.is_closed = true

        $httpBackend.expectPOST('/case/reopen/501/', 'note=Hello+there').respond('')
        CaseService.reopen(testCase, "Hello there").then(() ->
          expect(testCase.is_closed).toEqual(false)
        )
        $httpBackend.flush()
      )
    )

    describe('startExport', () ->
      it('posts to export endpoint', () ->
        $httpBackend.expectPOST('/caseexport/create/?folder=open').respond('')
        CaseService.startExport({folder: "open"})
        $httpBackend.flush()
      )
    )
  )

  describe('LabelService', () ->
    LabelService = null
    testLabel = {id: 123, name: "Test Label"}

    beforeEach(inject((_LabelService_) ->
      LabelService = _LabelService_
    ))

    describe('delete', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/label/delete/123/').respond("")
        LabelService.delete(testLabel)
        $httpBackend.flush()
      )
    )
  )

  describe('MessageService', () ->
    MessageService = null
    testMessages = [
      {id: 101, text: "Hello 1", flagged: true},
      {id: 102, text: "Hello 2", flagged: false}
    ]

    beforeEach(inject((_MessageService_) ->
      MessageService = _MessageService_
    ))

    describe('fetchHistory', () ->
      it('fetches from history endpoint', () ->
        $httpBackend.expectGET('/message/history/101/').respond('{"actions":[{"action":"archive","created_on":"2016-05-17T08:49:13.698864"}]}')
        MessageService.fetchHistory(testMessages[0]).then((actions) ->
          expect(actions).toEqual([{action: "archive", "created_on": utcdate(2016, 5, 17, 8, 49, 13, 698)}])
        )
        $httpBackend.flush()
      )
    )

    describe('flagMessages', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/message/action/flag/').respond('')
        MessageService.flagMessages(testMessages, true, null)
        $httpBackend.flush()

        expect(testMessages[0].flagged).toEqual(true)
        expect(testMessages[1].flagged).toEqual(true)
      )
    )

    describe('startExport', () ->
      it('posts to export endpoint', () ->
        $httpBackend.expectPOST('/messageexport/create/?archived=0&folder=inbox').respond('')
        MessageService.startExport({folder: "inbox"})
        $httpBackend.flush()
      )
    )
  )

  describe('OutgoingService', () ->
    OutgoingService = null
    testPartner = {id: 123, name: "McTest Partners Ltd"}

    beforeEach(inject((_OutgoingService_) ->
      OutgoingService = _OutgoingService_
    ))

    describe('startReplyExport', () ->
      it('posts to export endpoint', () ->
        $httpBackend.expectPOST('/replyexport/create/?partner=123').respond('')
        OutgoingService.startReplyExport({partner: testPartner})
        $httpBackend.flush()
      )
    )
  )

  describe('PartnerService', () ->
    PartnerService = null
    testPartner = {id: 123, name: "McTest Partners Ltd"}

    beforeEach(inject((_PartnerService_) ->
      PartnerService = _PartnerService_
    ))

    describe('fetchUsers', () ->
      it('fetches from users endpoint', () ->
        $httpBackend.expectGET('/partner/users/123/').respond('{"results":[{"id": 123, "name": "Tom McTest"}]}')
        PartnerService.fetchUsers(testPartner).then((users) ->
          expect(users).toEqual([{id: 123, name: "Tom McTest"}])
        )
        $httpBackend.flush()
      )
    )

    describe('delete', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/partner/delete/123/').respond('')
        PartnerService.delete(testPartner)
        $httpBackend.flush()
      )
    )
  )

  describe('UserService', () ->
    UserService = null
    testUser = {id: 123, name: "Tom McTest"}

    beforeEach(inject((_UserService_) ->
      UserService = _UserService_
    ))

    describe('delete', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/user/delete/123/').respond('')
        UserService.delete(testUser)
        $httpBackend.flush()
      )
    )
  )
)
