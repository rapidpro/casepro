# Unit tests for our Javascript utilities

describe('utils:', () ->

  describe('formatIso8601', () ->
    it('formats a date string', () ->
      expect(utils.formatIso8601(new Date(Date.UTC(2016, 4, 17, 8, 49, 13, 698)))).toEqual("2016-05-17T08:49:13.698Z")
    )
  )

  describe('parseIso8601', () ->
    it('parses a date string', () ->
      expect(utils.parseIso8601("2016-05-17T08:49:13.698")).toEqual(new Date(Date.UTC(2016, 4, 17, 8, 49, 13, 698)))
      expect(utils.parseIso8601("2016-05-17T08:49:13.698864")).toEqual(new Date(Date.UTC(2016, 4, 17, 8, 49, 13, 698)))
      expect(utils.parseIso8601("2016-05-17T08:49:13.698864Z")).toEqual(new Date(Date.UTC(2016, 4, 17, 8, 49, 13, 698)))
    )
  )
  
  describe('toFormData', () ->
    it('constructs a FormData from an object', () ->
      data = utils.toFormData({a: 1, b: "x", c: [2, 3], d: null})

      # TODO

      # expect(Array.from(data.keys())).toEqual([])
    )
  )
)
