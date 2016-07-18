# Unit tests for our Angular directives

describe('directives:', () ->
  #=======================================================================
  # Tests for pod
  #=======================================================================
  describe('cpPod', () ->
    $rootScope = null
    $compile = null

    beforeEach(module('templates'))
    beforeEach(module('cases'))

    beforeEach(inject((_$rootScope_, _$compile_) ->
      $rootScope = _$rootScope_
      $compile = _$compile_

      $rootScope.podConfig = {title: 'Foo'}
      $rootScope.podData = {items: []}
    ))

    it('should draw the pod items', () ->
      $rootScope.podConfig.title = 'Foo'

      el = $compile('<div cp-pod></div>')($rootScope)[0]
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

      el = $compile('<div cp-pod></div>')($rootScope)[0]
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
)
