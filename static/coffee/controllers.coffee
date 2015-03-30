controllers = angular.module('upartners.controllers', ['upartners.services']);

#============================================================================
# Label messages controller
#============================================================================
controllers.controller 'LabelMessagesController', [ '$scope', 'MessageService', ($scope, MessageService) ->

  $scope.messages = []
  $scope.selected = []
  $scope.loading_old = false
  $scope.has_older = true

  $scope.init = (label_id) ->
    $scope.label_id = label_id
    $scope.loadOldMessages()

  #============================================================================
  # Loads old messages - called by infinite scroller
  #============================================================================
  $scope.loadOldMessages = ->
    $scope.loading_old = true

    MessageService.fetchOldMessages $scope.label_id, 1, (messages, has_older) ->
      $scope.messages = $scope.messages.concat messages
      $scope.has_older = has_older
      $scope.loading_old = false

  $scope.toggleMessageFlag = (message) ->
    old_state = message.flagged
    message.flagged = !old_state

    if old_state != message.flagged
      MessageService.flagMessages([message.id], message.flagged)

  $scope.selectionUpdate = () ->
    $scope.selected = (msg.id for msg in $scope.messages when msg.selected)

  $scope.archiveSelection = () ->
    alert("TODO: archive: " + $scope.selected)
]
