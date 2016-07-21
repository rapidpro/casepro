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

  describe('fieldvalue', () ->
    $filter = null

    beforeEach(() ->
      inject(( _$filter_) ->
        $filter = _$filter_
      )
    )

    it('it looksup and formats value based on type', () ->
      $scope = $rootScope.$new()
      $scope.ann = {id: 401, name: "Ann", fields: {nid: 1234567, edd: '2016-07-04T12:59:46.309033Z'}}
      $scope.myfields = [
        {key: 'nid', label: "NID", value_type:'N'},
        {key: 'edd', label: "EDD", value_type:'D'},
        {key: 'nickname', label: "Nickname", value_type:'T'}
      ]

      # check numerical field
      element = $compile('<cp-fieldvalue contact="ann" field="myfields[0]" />')($scope)
      $rootScope.$digest()

      expect(element.isolateScope().contact).toEqual($scope.ann)
      expect(element.isolateScope().field).toEqual($scope.myfields[0])
      expect(element.isolateScope().value).toEqual("1,234,567")
      expect(element.text()).toEqual("1,234,567")

      # check date field
      element = $compile('<cp-fieldvalue contact="ann" field="myfields[1]" />')($scope)
      $rootScope.$digest()

      expect(element.text()).toEqual("Jul 4, 2016")

      # check field with no value
      element = $compile('<cp-fieldvalue contact="ann" field="myfields[2]" />')($scope)
      $rootScope.$digest()

      expect(element.text()).toEqual("")
    )
  )
)
