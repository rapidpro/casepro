filters = angular.module('upartners.filters', []);

filters.filter 'autodate', (dateFilter) ->
  (date) ->
    dateFilter(date, 'MMM dd, yyyy')


filters.filter 'reverse', () ->
  (items) ->
    items.slice().reverse()
