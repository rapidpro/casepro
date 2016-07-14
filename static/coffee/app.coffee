app = angular.module('cases', [
  'ngSanitize',
  'ngAnimate',
  'ui.bootstrap',
  'ui.select',
  'infinite-scroll',
  'cases.services',
  'cases.controllers',
  'cases.filters',
  'cases.directives'
]);

app.config [ '$interpolateProvider', '$httpProvider', ($interpolateProvider, $httpProvider) ->
  # Since Django uses {{ }}, we will have angular use [[ ]] instead.
  $interpolateProvider.startSymbol "[["
  $interpolateProvider.endSymbol "]]"

  # so that HttpRequest.is_ajax() works
  $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest'

  # Use Django's CSRF functionality
  $httpProvider.defaults.xsrfCookieName = 'csrftoken'
  $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'

  $httpProvider.useApplyAsync(true);
]
