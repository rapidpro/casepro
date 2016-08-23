# Unit tests for our Javascript utilities

describe('utils:', () ->

  describe('formatIso8601', () ->
    it('formats a date string', () ->
      expect(utils.formatIso8601(null)).toEqual(null)
      expect(utils.formatIso8601(utcdate(2016, 5, 17, 8, 49, 13, 698))).toEqual("2016-05-17T08:49:13.698Z")
      expect(utils.formatIso8601(utcdate(2016, 5, 17, 8, 49, 13, 698), true)).toEqual("2016-05-17T08:49:13.698Z")
      expect(utils.formatIso8601(utcdate(2016, 5, 17, 8, 49, 13, 698), false)).toEqual("2016-05-17")
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

  describe('addMonths', () ->
    it('adds the given number of months to the given date', () ->
      expect(utils.addMonths(utcdate(2016, 1, 31, 8, 49, 0, 0), 2)).toEqual(utcdate(2016, 3, 31, 8, 49, 0, 0))
      expect(utils.addMonths(utcdate(2016, 5, 17, 8, 49, 0, 0), -1)).toEqual(utcdate(2016, 4, 17, 8, 49, 0, 0))
      expect(utils.addMonths(utcdate(2016, 1, 31, 8, 49, 0, 0), 3)).toEqual(utcdate(2016, 4, 30, 8, 49, 0, 0))
    )
  )

  describe('find', () ->
    it('finds first item in a list with the given property value', () ->
      items = [{foo: 1, bar: "X"}, {foo: 3, bar: "Y"}, {foo: 5, bar: "Z"}, {foo: 3, bar: "Z"}]

      expect(utils.find(items, 'foo', 3)).toEqual({foo: 3, bar: "Y"})
      expect(utils.find(items, 'bar', "Z")).toEqual({foo: 5, bar: "Z"})
    )
  )

  describe('trap', () ->
    it('should call the accept function for values of the given type', () ->
      class Foo
      foo = new Foo()
      expect(utils.trap(Foo, ((v) -> v), (-> null))(foo)).toEqual(foo)
    )

    it('should call the reject function for values not of the given type', () ->
      class Foo
      class Bar
      bar = new Bar()
      expect(utils.trap(Foo, ((v) -> v), (-> null))(bar)).toEqual(null)
    )
  )
)
