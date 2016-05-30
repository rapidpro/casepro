# Unit tests for our Angular services (services listed A-Z)

describe('services:', () ->
  $httpBackend = null
  data = null

  beforeEach(() ->
    module('cases')

    inject((_$httpBackend_) ->
      $httpBackend = _$httpBackend_
    )

    data = {
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

  #=======================================================================
  # Tests for CaseService
  #=======================================================================
  describe('CaseService', () ->
    CaseService = null

    beforeEach(inject((_CaseService_) ->
      CaseService = _CaseService_

      data.case1 = {
        id: 501,
        summary: "Got tea?",
        labels: [data.tea],
        assignee: data.moh,
        opened_on: utcdate(2016, 5, 27, 11, 0, 0, 0),
        is_closed: false
      }
    ))
    
    describe('addNote', () ->
      it('posts to note endpoint', () ->
        $httpBackend.expectPOST('/case/note/501/').respond('')
        CaseService.addNote(data.case1, "Hello there")
        $httpBackend.flush()
      )
    )

    describe('reassign', () ->
      it('posts to reassign endpoint', () ->
        $httpBackend.expectPOST('/case/reassign/501/').respond('')
        CaseService.reassign(data.case1, data.who).then(() ->
          expect(data.case1.assignee).toEqual(data.who)
        )
        $httpBackend.flush()
      )
    )

    describe('close', () ->
      it('posts to close endpoint and closes case', () ->
        $httpBackend.expectPOST('/case/close/501/').respond('')
        CaseService.close(data.case1, "Hello there").then(() ->
          expect(data.case1.is_closed).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('open', () ->
      it('posts to open endpoint', () ->
        $httpBackend.expectPOST('/case/open/').respond('{"case": {"id": 501}, "is_new": true}')
        CaseService.open({id: 401, text: "Hi"}, "Hi", data.moh).then((caseObj) ->
          expect(caseObj.id).toEqual(501)
          expect(caseObj.isNew).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('relabel', () ->
      it('posts to label endpoint', () ->
        $httpBackend.expectPOST('/case/label/501/').respond('')
        CaseService.relabel(data.case1, [data.coffee]).then(() ->
          expect(data.case1.labels).toEqual([data.coffee])
        )
        $httpBackend.flush()
      )
    )

    describe('reopen', () ->
      it('posts to reopen endpoint and reopens case', () ->
        data.case1.is_closed = true

        $httpBackend.expectPOST('/case/reopen/501/').respond('')
        CaseService.reopen(data.case1, "Hello there").then(() ->
          expect(data.case1.is_closed).toEqual(false)
        )
        $httpBackend.flush()
      )
    )
    
    describe('replyTo', () ->
      it('posts to reply endpoint', () ->
        $httpBackend.expectPOST('/case/reply/501/').respond('')
        CaseService.replyTo(data.case1, "Hello there")
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

    describe('updateSummary', () ->
      it('posts to update summary endpoint', () ->
        $httpBackend.expectPOST('/case/update_summary/501/').respond('')
        CaseService.updateSummary(data.case1, "Got coffee?").then(() ->
          expect(data.case1.summary).toEqual("Got coffee?")
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
        $httpBackend.expectPOST('/label/delete/201/').respond("")
        LabelService.delete(data.tea)
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

      data.msg1 = {id: 101, text: "Hello 1", labels: [data.tea], flagged: true, archived: false}
      data.msg2 = {id: 102, text: "Hello 2", labels: [data.coffee], flagged: false, archived: false}
    ))

    describe('fetchHistory', () ->
      it('fetches from history endpoint', () ->
        $httpBackend.expectGET('/message/history/101/').respond('{"actions":[{"action":"archive","created_on":"2016-05-17T08:49:13.698864"}]}')
        MessageService.fetchHistory(data.msg1).then((actions) ->
          expect(actions).toEqual([{action: "archive", "created_on": utcdate(2016, 5, 17, 8, 49, 13, 698)}])
        )
        $httpBackend.flush()
      )
    )

    describe('bulkArchive', () ->
      it('posts to bulk action endpoint', () ->
        $httpBackend.expectPOST('/message/action/archive/').respond('')
        MessageService.bulkArchive([data.msg1, data.msg2]).then(() ->
          expect(data.msg1.archived).toEqual(true)
          expect(data.msg2.archived).toEqual(true)
        )
        $httpBackend.flush()
      )
    )

    describe('bulkFlag', () ->
      it('posts to bulk action endpoint', () ->
        $httpBackend.expectPOST('/message/action/flag/').respond('')
        MessageService.bulkFlag([data.msg1, data.msg2], true).then(() ->
          expect(data.msg1.flagged).toEqual(true)
          expect(data.msg2.flagged).toEqual(true)
        )
        $httpBackend.flush()

        $httpBackend.expectPOST('/message/action/unflag/').respond('')
        MessageService.bulkFlag([data.msg1, data.msg2], false).then(() ->
          expect(data.msg1.flagged).toEqual(false)
          expect(data.msg2.flagged).toEqual(false)
        )
        $httpBackend.flush()
      )
    )

    describe('bulkLabel', () ->
      it('posts to bulk action endpoint', () ->
        $httpBackend.expectPOST('/message/action/label/').respond('')
        MessageService.bulkLabel([data.msg1, data.msg2], data.tea).then(() ->
          expect(data.msg1.labels).toEqual([data.tea])
          expect(data.msg2.labels).toEqual([data.coffee, data.tea])
        )
        $httpBackend.flush()
      )
    )

    describe('bulkReply', () ->
      it('posts to bulk reply endpoint', () ->
        $httpBackend.expectPOST('/message/bulk_reply/').respond('')
        MessageService.bulkReply([data.msg1, data.msg2], "Welcome")
        $httpBackend.flush()
      )
    )

    describe('bulkRestore', () ->
      it('posts to bulk action endpoint', () ->
        $httpBackend.expectPOST('/message/action/restore/').respond('')
        MessageService.bulkRestore([data.msg1, data.msg2]).then(() ->
          expect(data.msg1.archived).toEqual(false)
          expect(data.msg2.archived).toEqual(false)
        )
        $httpBackend.flush()
      )
    )

    describe('forward', () ->
      it('posts to forward endpoint', () ->
        $httpBackend.expectPOST('/message/forward/101/').respond('')
        MessageService.forward(data.msg1, "Welcome", {urn: "tel:+260964153686"})
        $httpBackend.flush()
      )
    )

    describe('relabel', () ->
      it('posts to label endpoint', () ->
        $httpBackend.expectPOST('/message/label/101/').respond('')
        MessageService.relabel(data.msg1, [data.coffee]).then(() ->
          expect(data.msg1.labels).toEqual([data.coffee])
        )
        $httpBackend.flush()
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

  #=======================================================================
  # Tests for OutgoingService
  #=======================================================================
  describe('OutgoingService', () ->
    OutgoingService = null

    beforeEach(inject((_OutgoingService_) ->
      OutgoingService = _OutgoingService_
    ))

    describe('startReplyExport', () ->
      it('posts to export endpoint', () ->
        $httpBackend.expectPOST('/replyexport/create/?partner=301').respond('')
        OutgoingService.startReplyExport({partner: data.moh})
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

    describe('fetchUsers', () ->
      it('fetches from users endpoint', () ->
        $httpBackend.expectGET('/partner/users/301/').respond('{"results":[{"id": 101, "name": "Tom McTest", "replies": {}}]}')
        PartnerService.fetchUsers(data.moh).then((users) ->
          expect(users).toEqual([{id: 101, name: "Tom McTest", replies: {}}])
        )
        $httpBackend.flush()
      )
    )

    describe('delete', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/partner/delete/301/').respond('')
        PartnerService.delete(data.moh)
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

    describe('delete', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/user/delete/101/').respond('')
        UserService.delete(data.user1)
        $httpBackend.flush()
      )
    )
  )
)
