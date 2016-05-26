describe('services:', () ->
  $httpBackend = null

  beforeEach(() ->
    module('cases')

    inject((_$httpBackend_) ->
      $httpBackend = _$httpBackend_
    )
  )

  describe('PartnerService', () ->
    PartnerService = null
    testPartner = {id: 123, name: "McTest Partners Ltd"}

    beforeEach(inject((_PartnerService_) ->
      PartnerService = _PartnerService_
    ))

    describe('deletePartner', () ->
      it('posts to delete endpoint', () ->
        $httpBackend.expectPOST('/partner/delete/123/').respond("")
        PartnerService.deletePartner(testPartner, null)
        $httpBackend.flush()
      )
    )
  )

  # TODO add tests for all services
)
