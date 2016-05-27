# Unit tests for our Javascript utilities

describe('utils:', () ->

  describe('formatIso8601', () ->
    it('formats a date string', () ->
      expect(utils.formatIso8601(null)).toEqual(null)
      expect(utils.formatIso8601(utcdate(2016, 5, 17, 8, 49, 13, 698))).toEqual("2016-05-17T08:49:13.698Z")
    )
  )

  describe('parseIso8601', () ->
    it('parses a date string', () ->
      expect(utils.parseIso8601(null)).toEqual(null)
      expect(utils.parseIso8601("2016-05-17T08:49:13.698")).toEqual(utcdate(2016, 5, 17, 8, 49, 13, 698))
      expect(utils.parseIso8601("2016-05-17T08:49:13.698864")).toEqual(utcdate(2016, 5, 17, 8, 49, 13, 698))
      expect(utils.parseIso8601("2016-05-17T08:49:13.698864Z")).toEqual(utcdate(2016, 5, 17, 8, 49, 13, 698))
    )
  )

  describe('parseDates', () ->
    it('parses date fields on all objects in array', () ->
      objs = [{id: 1, time: "2016-05-17T08:49:13.698864"}, {id: 2, time: "2015-04-16T08:49:13.698864"}]

      expect(utils.parseDates(objs, 'time')).toEqual([
        {id: 1, time: utcdate(2016, 5, 17, 8, 49, 13, 698)}, {id: 2, time: utcdate(2015, 4, 16, 8, 49, 13, 698)}
      ])
    )
  )
)
