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
  $scope.totalMessages = 0

  $scope.init = (labelId) ->
    $scope.labelId = labelId

    $scope.loadOldMessages()

  #============================================================================
  # Message fetching
  #============================================================================

  $scope.loadOldMessages = ->
    $scope.loadingOld = true

    MessageService.fetchOldMessages $scope.labelId, $scope.page, $scope.search, (messages, total, hasOlder) ->
      if $scope.page == 1
        $scope.messages = messages
      else
        $scope.messages = $scope.messages.concat messages

      $scope.hasOlder = hasOlder
      $scope.page += 1
      $scope.totalMessages = total
      $scope.loadingOld = false

  $scope.onMessageSearch = () ->
    $scope.activeSearch = $scope.search
    $scope.page = 1
    $scope.loadOldMessages()

  $scope.toggleMessageFlag = (message) ->
    prevState = message.flagged
    message.flagged = !prevState
    MessageService.flagMessages([message], message.flagged)

  #============================================================================
  # Selection controls
  #============================================================================

  $scope.selectAll = () ->
    for msg in $scope.messages
      msg.selected = true
    $scope.updateSelection()

  $scope.selectNone = () ->
    for msg in $scope.messages
      msg.selected = false
    $scope.selection = []

  $scope.updateSelection = () ->
    $scope.selection = (msg for msg in $scope.messages when msg.selected)

  #============================================================================
  # Selection actions
  #============================================================================

  $scope.labelSelection = (label) ->
    _showConfirm 'Apply the label <strong>' + label + '</strong> to the selected messages?', () ->
      MessageService.labelMessages($scope.selection, label)

  $scope.flagSelection = () ->
    _showConfirm 'Flag the selected messages?', () ->
      MessageService.flagMessages($scope.selection, true)

  $scope.caseForSelection = () ->
    _showConfirm 'Open a new case for the selected message?', () ->
      alert("TODO: open case for: " + $scope.selection)

  $scope.replyToSelection = () ->
    alert("TODO: reply to: " + $scope.selection)

  $scope.forwardSelection = () ->
    alert("TODO: forward: " + $scope.selection)

  $scope.archiveSelection = () ->
    _showConfirm 'Archive the selected messages? This will remove them from the inbox.', () ->
      MessageService.archiveMessages($scope.selection)

  #============================================================================
  # Support functions
  #============================================================================

  _showConfirm = (prompt, callback) ->
    $modal.open({templateUrl: 'confirmModal.html', controller: 'ConfirmModalController', resolve: {prompt: () -> prompt}})
    .result.then () ->
      callback()
]


#============================================================================
# Confirmation modal dialog controller
#============================================================================

controllers.controller 'ConfirmModalController', [ '$scope', '$modalInstance', 'prompt', ($scope, $modalInstance, prompt) ->
  $scope.prompt = prompt
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