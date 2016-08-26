angular.module('cases.controllers')
  .controller('DummyPodController', ['$scope', 'PodApi', ($scope, PodApi) ->
    $scope.init = (id, config) ->
      $scope.podId = id
      $scope.podConfig = config

      return PodApi.get($scope.podId)
        .then((d) -> $scope.podData = d)
  ])


angular.module('cases.directives')
  .directive('dummyPod', -> {
    templateUrl: '/sitestatic/templates/pods/dummy.html'
  })
