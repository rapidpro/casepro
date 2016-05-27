# Unit tests for our Angular services

describe('services:', () ->
  $httpBackend = null

  beforeEach(() ->
    module('cases')

    inject((_$httpBackend_) ->
      $httpBackend = _$httpBackend_
    )
  )

  describe('LabelService', () ->
    LabelService = null
    testLabel = {id: 123, name: "Test Label"}

    beforeEach(inject((_LabelService_) ->
      LabelService = _LabelService_
    ))

    describe('deleteLabel', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/label/delete/123/').respond("")
        LabelService.deleteLabel(testLabel)
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

    describe('deletePartner', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/partner/delete/123/').respond('')
        PartnerService.deletePartner(testPartner)
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

    describe('deleteUser', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/user/delete/123/').respond('')
        UserService.deleteUser(testUser)
        $httpBackend.flush()
      )
    )
  )
)
