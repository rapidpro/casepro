app = angular.module('cases', [
  'ngSanitize',
  'ui.bootstrap',
  'ui.select',
  'infinite-scroll',
  'cases.services',
  'cases.controllers',
  'cases.filters'
]);

app.config [ '$interpolateProvider', '$httpProvider', ($interpolateProvider, $httpProvider) ->
  # Since Django uses {{ }}, we will have angular use [[ ]] instead.
  $interpolateProvider.startSymbol "[["
  $interpolateProvider.endSymbol "]]"

  # Use Django's CSRF functionality
  $httpProvider.defaults.xsrfCookieName = 'csrftoken'
  $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'

  $httpProvider.useApplyAsync(true);
]
