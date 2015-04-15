app = angular.module('upartners', [
  'ngSanitize',
  'ui.bootstrap',
  'ui.select',
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
