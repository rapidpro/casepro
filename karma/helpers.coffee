
# helper for creating UTC datetimes
utcdate = (y, m, d, h, min, sec, ms) ->
  return new Date(Date.UTC(y, m - 1, d, h, min, sec, ms))
