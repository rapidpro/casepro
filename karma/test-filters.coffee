# Unit tests for our Angular filters

describe('filters:', () ->
  $filter = null

  beforeEach(() ->
    module('cases')

    inject((_$filter_) ->
      $filter = _$filter_
    )

    jasmine.clock().install()
  )

  afterEach(() ->
    jasmine.clock().uninstall()
  )

  describe('reverse', () ->
    it('reverses an array', () ->
      reverse = $filter('reverse')
      expect(reverse([1, 2, 3])).toEqual([3, 2, 1])
    )
  )

  describe('autodate', () ->
    it('formats a date', () ->
      jasmine.clock().mockDate(new Date(2015, 1, 1));  # Feb 1 2015
      
      autodate = $filter('autodate')
      expect(autodate(new Date(2015, 1, 1, 10, 0))).toEqual("10:00")  # same day
      expect(autodate(new Date(2015, 2, 1, 11, 0))).toEqual("Mar 1")  # same year
      expect(autodate(new Date(2014, 1, 1, 10, 0))).toEqual("Feb 1, 2014")  # year before
      expect(autodate(new Date(2016, 1, 1, 10, 0))).toEqual("Feb 1, 2016")  # year after
    )
  )

  describe('urlencode', () ->
    it('encodes URL components', () ->
      urlencode = $filter('urlencode')
      expect(urlencode("A & B ?")).toEqual("A%20%26%20B%20%3F")
    )
  )

  describe('deunderscore', () ->
    it('replaces underscores with spaces', () ->
      deunderscore = $filter('deunderscore')
      expect(deunderscore("A_B__C_")).toEqual("A B  C ")
    )
  )
)
