# Unit tests for our Angular directives

describe('directives:', () ->
  $compile = null
  $rootScope = null
  $templateCache = null
  $q = null
  $filter = null

  beforeEach(() ->
    module('templates')
    module('cases')

    inject((_$compile_, _$rootScope_, _$templateCache_, _$q_, _$filter_) ->
      $compile = _$compile_
      $rootScope = _$rootScope_
      $templateCache = _$templateCache_
      $q = _$q_
      $filter = _$filter_
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

  #=======================================================================
  # Tests for date tooltip
  #=======================================================================
  describe('cpDate', () ->

    it('adds tooltip at the specified position on the date', () ->
      $scope = $rootScope.$new()
      $scope.time = new Date "December 25, 2016 23:15:00"

      template = $compile('<cp-date time="time" tooltip-position="top-left" />')
      element = template($scope)[0]
      $rootScope.$digest()

      autodate = $filter('autodate')
      expect(element.textContent).toMatch(autodate($scope.time))

      div = element.querySelector('div')
      expect(div.hasAttribute("uib-tooltip")).toBe(true)
      fulldate = $filter('fulldate')
      expect(div.getAttribute("uib-tooltip")).toEqual(fulldate($scope.time))
      expect(div.hasAttribute("tooltip-placement")).toBe(true)
      expect(div.getAttribute("tooltip-placement")).toEqual("top-left")
    )

    it('adds tooltip at default position on the date', () ->
      $scope = $rootScope.$new()
      $scope.time = new Date "December 25, 2016 23:15:00"

      template = $compile('<cp-date time="time" />')
      element = template($scope)[0]
      $rootScope.$digest()

      autodate = $filter('autodate')
      expect(element.textContent).toMatch(autodate($scope.time))

      div = element.querySelector('div')
      expect(div.hasAttribute("uib-tooltip")).toBe(true)
      fulldate = $filter('fulldate')
      expect(div.getAttribute("uib-tooltip")).toEqual(fulldate($scope.time))
      expect(div.hasAttribute("tooltip-placement")).toBe(true)
      expect(div.getAttribute("tooltip-placement")).toEqual("top-right")
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

      expect(element.text()).toEqual("--")
    )
  )

  #=======================================================================
  # Tests for URN
  #=======================================================================
  describe('cpUrn', () ->
    it('formats a URN as a link', () ->
      $scope = $rootScope.$new()
      $scope.urn = 'tel:+11234567890'

      el = $compile('<cp-urn urn="urn" />')($scope)[0]
      $rootScope.$digest()

      link = el.querySelector('a')
      expect(link.href).toEqual('tel:+11234567890')
      expect(link.textContent).toEqual('+11234567890')

      $scope.urn = 'twitter:bobby'

      el = $compile('<cp-urn urn="urn" />')($scope)[0]
      $rootScope.$digest()

      link = el.querySelector('a')
      expect(link.href).toEqual('https://twitter.com/bobby')
      expect(link.textContent).toEqual('bobby')

      $scope.urn = 'mailto:jim@unicef.org'

      el = $compile('<cp-urn urn="urn" />')($scope)[0]
      $rootScope.$digest()

      link = el.querySelector('a')
      expect(link.href).toEqual('mailto:jim@unicef.org')
      expect(link.textContent).toEqual('jim@unicef.org')
    )
  )
)
