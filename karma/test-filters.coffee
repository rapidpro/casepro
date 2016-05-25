describe('filters:reverse', () ->
  $filter = null

  beforeEach(module('cases'))

  beforeEach(inject((_$filter_) ->
    $filter = _$filter_
  ))

  it('reverses an array', () ->
    reverse = $filter('reverse')
    expect(reverse([1, 2, 3])).toEqual([3, 2, 1])
  )
)
