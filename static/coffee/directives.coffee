directives = angular.module('cases.directives', []);


#----------------------------------------------------------------------------
# A contact reference which displays a popover when hovered over
#----------------------------------------------------------------------------
directives.directive('cpContact', () ->
  return {
    restrict: 'E',
    scope: {contact: '=', fields: '='},
    templateUrl: '/partials/directive_contact.html',
    controller: ['$scope', 'ContactService', ($scope, ContactService) ->
      $scope.fetched = false
      $scope.popoverIsOpen = false
      $scope.popoverTemplateUrl = '/partials/popover_contact.html'

      $scope.openPopover = () ->
        $scope.popoverIsOpen = true

        if not $scope.fetched
          ContactService.fetch($scope.contact.id).then((contact) ->
            $scope.contact = contact
            $scope.fetched = true
          )
      
      $scope.closePopover = () ->
        $scope.popoverIsOpen = false
    ]      
  }
)

#----------------------------------------------------------------------------
# A contact field value
#----------------------------------------------------------------------------
directives.directive('cpFieldvalue', () ->
  return {
    restrict: 'E',
    scope: {contact: '=', field: '='},
    template: '[[ value ]]',
    controller: ['$scope', '$filter', ($scope, $filter) ->
      raw = $scope.contact.fields[$scope.field.key]

      if raw
        if $scope.field.value_type == 'N'
          $scope.value = $filter('number')(raw)
        else if $scope.field.value_type == 'D'
          $scope.value = $filter('date')(raw, 'mediumDate')
        else
          $scope.value = raw
      else
        $scope.value = '--'
    ]
  }
)

#----------------------------------------------------------------------------
# A phone URN value
#----------------------------------------------------------------------------
directives.directive('phoneurn', () ->
  return {
    require: 'ngModel',
    link: (scope, elm, attrs, ctrl) ->
      ctrl.$validators.phoneurn = (modelValue, viewValue) ->
        if scope.fields.urn.scheme != "tel"
          return true
        if !viewValue
          # We let required take care of empty inputs to give better error message
          return true
        phoneUtil = i18n.phonenumbers.PhoneNumberUtil.getInstance()

        try
          parsed = phoneUtil.parse(viewValue)
        catch error
          return false

        if viewValue != phoneUtil.format(parsed, i18n.phonenumbers.PhoneNumberFormat.E164)
            return false

        if !phoneUtil.isPossibleNumber(parsed) || !phoneUtil.isValidNumber(parsed)
            return false

        return true
  }
)


directives.directive('cpAlert', -> {
  restrict: 'E',
  transclude: true,
  scope: {type: '@'},
  templateUrl: '/sitestatic/templates/alert.html'
})


directives.directive('cpAlerts', -> {
  templateUrl: '/sitestatic/templates/alerts.html',
  scope: {alerts: '='}
})


#----------------------------------------------------------------------------
# Pod directive
#----------------------------------------------------------------------------
directives.directive('cpPod', -> {
  templateUrl: -> '/sitestatic/templates/pod.html'
})

#----------------------------------------------------------------------------
# Date formatter
#----------------------------------------------------------------------------
directives.directive('cpDate', () ->
  return {
    restrict: 'E',
    scope: {time: '=', tooltipPosition: '@'},
    templateUrl: '/sitestatic/templates/date.html',
    controller: ($scope) ->
        if $scope.tooltipPosition is undefined
            $scope.tooltipPosition = "top-right";
  }
)

#----------------------------------------------------------------------------
# URN as link renderer
#----------------------------------------------------------------------------
directives.directive('cpUrn', () ->
  return {
    restrict: 'E',
    scope: {urn: '='},
    template: '<a href="[[ link ]]">[[ path ]]</a>',
    controller: ['$scope', ($scope) ->
        parts = $scope.urn.split(':')
        $scope.scheme = parts[0]
        $scope.path = parts[1]

        if $scope.scheme == 'twitter'
          $scope.link = 'https://twitter.com/' + $scope.path
        else
          $scope.link = $scope.urn
    ]
  }
)
