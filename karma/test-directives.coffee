# Unit tests for our Angular directives

describe('directives:', () ->
  $compile = null
  $rootScope = null
  $templateCache = null
  $q = null

  beforeEach(() ->
    module('templates')
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

      fetch = spyOnPromise($q, $scope, ContactService, 'fetch')

      element = $compile('<cp-contact contact="ann" />')($scope)
      $rootScope.$digest()

      expect(element.html()).toContain("Ann");

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
  # Tests for pod
  #=======================================================================
  describe('cpPod', () ->
    $rootScope = null
    $compile = null

    beforeEach(inject((_$rootScope_, _$compile_) ->
      $rootScope = _$rootScope_
      $compile = _$compile_

      $rootScope.podConfig = {title: 'Foo'}
      $rootScope.podData = {items: []}
    ))

    it('should draw the pod items', () ->
      $rootScope.podConfig.title = 'Foo'

      el = $compile('<cp-pod/>')($rootScope)[0]
      $rootScope.$digest()

      expect(el.querySelector('.pod-title').textContent).toContain('Foo')
    )

    it('should draw the pod items', ->
      $rootScope.podData = {
        items: [{
          name: 'Bar'
          value: 'Baz'
        }, {
          name: 'Quux'
          value: 'Corge'
        }]
      }

      el = $compile('<cp-pod/>')($rootScope)[0]
      $rootScope.$digest()

      item1 = el.querySelector('.pod-item:nth-child(1)')
      item2 = el.querySelector('.pod-item:nth-child(2)')

      expect(item1.querySelector('.pod-item-name').textContent)
        .toContain('Bar')

      expect(item1.querySelector('.pod-item-value').textContent)
        .toContain('Baz')

      expect(item2.querySelector('.pod-item-name').textContent)
        .toContain('Quux')

      expect(item2.querySelector('.pod-item-value').textContent)
        .toContain('Corge')
    )
  )

  #=======================================================================
  # Tests for pod
  #=======================================================================
  describe('cpNotifications', () ->
    $rootScope = null
    $compile = null

    beforeEach(inject((_$rootScope_, _$compile_) ->
      $rootScope = _$rootScope_
      $compile = _$compile_

      $rootScope.notifications = []
      $rootScope.removeNotification = ->
    ))

    it('should draw the notifications', () ->
      $rootScope.notifications = [{
        type: 'danger',
        message: 'Foo'
      }, {
        type: 'success',
        message: 'Bar'
      }]

      el = $compile('<cp-notifications></cp-notifications>')($rootScope)[0]
      $rootScope.$digest()

      notification1 = el.querySelector('.alert:nth-child(1)')
      notification2 = el.querySelector('.alert:nth-child(2)')

      expect(notification1.classList.contains('alert-danger')).toBe(true)
      expect(notification1.textContent).toMatch('Foo')

      expect(notification2.classList.contains('alert-success')).toBe(true)
      expect(notification2.textContent).toMatch('Bar')
    )

    it('should call removeNotification() when a notification is closed', ->
      $rootScope.notifications = [{
        type: 'danger',
        message: 'Foo'
      }, {
        type: 'success',
        message: 'Bar'
      }]

      $rootScope.removeNotification = jasmine.createSpy('removeNotification')

      el = $compile('<cp-notifications></cp-notifications>')($rootScope)[0]
      $rootScope.$digest()

      angular.element(el.querySelector('.alert:nth-child(2) .close'))
        .triggerHandler('click')

      expect($rootScope.removeNotification.calls.mostRecent().args[0])
        .toEqual(jasmine.objectContaining({
          type: 'success',
          message: 'Bar'
        }))
    )
  )
)
