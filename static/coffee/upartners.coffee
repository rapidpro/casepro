app = angular.module('upartners', [
  'ui.bootstrap',
  'infinite-scroll',
  'upartners.services',
  'upartners.controllers',
  'upartners.filters'
]);

app.config [ '$interpolateProvider', '$httpProvider', ($interpolateProvider, $httpProvider) ->
  # Since Django uses {{ }}, we will have angular use [[ ]] instead.
  $interpolateProvider.startSymbol "[["
  $interpolateProvider.endSymbol "]]"

  # Use Django's CSRF functionality
  $httpProvider.defaults.xsrfCookieName = 'csrftoken'
  $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'

  # Disabled since we reverted to Angular 1.2.x
  # $httpProvider.useApplyAsync(true);
]

$ ->
  # initialize select2 widgets
  $('.select2').each ->
    $(this).select2({ theme: "bootstrap" })

  # initialize datetime picker widgets
  #$('.datepicker').each ->
  #  $(this).datetimepicker({
  #    format: 'MMM DD, YYYY',
  #    maxDate: new Date()
  #  })

