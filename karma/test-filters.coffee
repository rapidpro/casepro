# Unit tests for our Angular filters

describe('filters:', () ->
  $filter = null

  beforeEach(() ->
    module('cases')

    inject((_$filter_) ->
      $filter = _$filter_
    )
  )

  describe('reverse', () ->
    it('reverses an array', () ->
      reverse = $filter('reverse')
      expect(reverse([1, 2, 3])).toEqual([3, 2, 1])
    )
  )

  describe('autodate', () ->
    jasmine.clock().mockDate(new Date(2015, 0, 1));  # Jan 1 2015

    it('formats a date', () ->
      autodate = $filter('autodate')
      expect(autodate(new Date(2015, 0, 1, 10, 0))).toEqual("10:00")  # same day
      expect(autodate(new Date(2015, 1, 1, 10, 0))).toEqual("Feb 1")  # same year
      expect(autodate(new Date(2014, 0, 1, 10, 0))).toEqual("Jan 1, 2014")
      expect(autodate(new Date(2014, 11, 31, 10, 0))).toEqual("Dec 31, 2014")
    )

    it('handles dates as strings', () ->
      autodate = $filter('autodate')
      expect(autodate("2014-12-31T10:00:00.000Z")).toEqual("Dec 31, 2014")
    )
  )
)
