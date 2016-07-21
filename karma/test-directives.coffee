# Unit tests for our Angular directives

describe('directives:', () ->
  $compile = null
  $rootScope = null
  $templateCache = null
  $q = null

  beforeEach(() ->
    module('cases')

    inject((_$compile_, _$rootScope_, _$templateCache_, _$q_) ->
      $compile = _$compile_
      $rootScope = _$rootScope_
      $templateCache = _$templateCache_
      $q = _$q_
    )
  )

  describe('contact', () ->
    ContactService = null

    beforeEach(() ->
      inject((_ContactService_) ->
        ContactService = _ContactService_
      )
    )

    it('replaces element', () ->
      $templateCache.put('/partials/directive_contact.html', '[[ contact.name ]]')
      $scope = $rootScope.$new()
      $scope.ann = {id: 401, name: "Ann"}
      $scope.myfields = [{key: 'age', label: "Age"}]

      fetch = spyOnPromise($q, $scope, ContactService, 'fetch')

      element = $compile('<cp-contact contact="ann" fields="myfields" />')($scope)
      $rootScope.$digest()

      expect(element.html()).toContain("Ann");

      expect(element.isolateScope().contact).toEqual($scope.ann)
      expect(element.isolateScope().fields).toEqual([{key: 'age', label: "Age"}])
      expect(element.isolateScope().fetched).toEqual(false)
      expect(element.isolateScope().popoverIsOpen).toEqual(false)
      expect(element.isolateScope().popoverTemplateUrl).toEqual('/partials/popover_contact.html')

      element.isolateScope().openPopover()

      expect(element.isolateScope().popoverIsOpen).toEqual(true)

      fetch.resolve({id: 401, name: "Ann", fields:{age: 35}})

      expect(element.isolateScope().fetched).toEqual(true)

      element.isolateScope().closePopover()

      expect(element.isolateScope().popoverIsOpen).toEqual(false)
    )
  )
)
