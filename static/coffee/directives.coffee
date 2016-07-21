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
