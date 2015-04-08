controllers = angular.module('upartners.controllers', ['upartners.services']);

#============================================================================
# Label messages controller
#============================================================================
controllers.controller 'LabelMessagesController', [ '$scope', '$modal', 'MessageService', ($scope, $modal, MessageService) ->

  $scope.messages = []
  $scope.selection = []
  $scope.loadingOld = false
  $scope.hasOlder = true
  $scope.search = { text: null, groups: [], after: null, before: null, reverse: false }
  $scope.activeSearch = {}
  $scope.page = 1

  $scope.init = (labelId) ->
    $scope.labelId = labelId
    $scope.loadOldMessages()

  #============================================================================
  # Loads old messages - called by infinite scroller
  #============================================================================
  $scope.loadOldMessages = ->
    $scope.loadingOld = true

    MessageService.fetchOldMessages $scope.labelId, $scope.page, $scope.search, (messages, hasOlder) ->
      if $scope.page == 1
        $scope.messages = messages
      else
        $scope.messages = $scope.messages.concat messages

      $scope.hasOlder = hasOlder
      $scope.page += 1
      $scope.loadingOld = false

  $scope.toggleMessageFlag = (message) ->
    prevState = message.flagged
    message.flagged = !prevState
    MessageService.flagMessages([message], message.flagged)

  $scope.isOtherLabel = (label) ->
    return label.id != $scope.labelId

  $scope.onMessageSearch = () ->
    $scope.activeSearch = $scope.search
    $scope.page = 1
    $scope.loadOldMessages()

  $scope.selectionUpdate = () ->
    $scope.selection = (msg for msg in $scope.messages when msg.selected)

  $scope.labelSelection = () ->
    $modal.open({templateUrl: 'labelModal.html', controller: 'LabelModalController', resolve: { selection: () -> return $scope.selection }})
    .result.then () ->
      alert('TODO: label ' + $scope.selection)

  $scope.flagSelection = () ->
    $modal.open({templateUrl: 'flagModal.html', controller: 'FlagModalController', resolve: { selection: () -> return $scope.selection }})
    .result.then () ->
      MessageService.flagMessages($scope.selection, true)

  $scope.caseForSelection = () ->
    alert("TODO: open cases for: " + $scope.selection)

  $scope.replyToSelection = () ->
    alert("TODO: reply to: " + $scope.selection)

  $scope.forwardSelection = () ->
    alert("TODO: forward: " + $scope.selection)

  $scope.archiveSelection = () ->
    $modal.open({templateUrl: 'archiveModal.html', controller: 'ArchiveModalController', resolve: { selection: () -> return $scope.selection }})
    .result.then () ->
      alert('TODO: archive ' + $scope.selection)
]


controllers.controller 'FlagModalController', [ '$scope', '$modalInstance', 'selection', ($scope, $modalInstance, selection) ->
  $scope.selection = selection
  $scope.ok = () -> $modalInstance.close(true)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]

controllers.controller 'LabelModalController', [ '$scope', '$modalInstance', 'selection', ($scope, $modalInstance, selection) ->
  $scope.selection = selection
  $scope.ok = () -> $modalInstance.close(true)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]

controllers.controller 'ArchiveModalController', [ '$scope', '$modalInstance', 'selection', ($scope, $modalInstance, selection) ->
  $scope.selection = selection
  $scope.ok = () -> $modalInstance.close(true)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#============================================================================
# Date range controller
#============================================================================
controllers.controller 'DateRangeController', [ '$scope', ($scope) ->
  $scope.afterOpen = false
  $scope.afterMin = null
  $scope.afterMax = new Date()
  $scope.beforeOpen = false
  $scope.beforeMin = null
  $scope.beforeMax = new Date()
  $scope.format = 'MMM dd, yyyy'

  $scope.openAfter = ($event) ->
    $event.preventDefault()
    $event.stopPropagation()
    $scope.afterOpen = true

  $scope.openBefore = ($event) ->
    $event.preventDefault()
    $event.stopPropagation()
    $scope.beforeOpen = true

  $scope.onAfterChange = () ->
    # don't allow before to be less than after
    $scope.beforeMin = $scope.search.after

  $scope.onBeforeChange = () ->
    # don't allow after to be more than before
    $scope.afterMax = $scope.search.before
]