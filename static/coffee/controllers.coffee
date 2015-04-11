controllers = angular.module('upartners.controllers', ['upartners.services']);


#============================================================================
# Label controller
#============================================================================

controllers.controller 'LabelController', [ '$scope', '$modal', '$window', ($scope, $modal, $window) ->

  $scope.init = (labelId) ->
    $scope.labelId = labelId

    $scope.partners = $window.contextData.partners
    $scope.labels = $window.contextData.labels
    $scope.otherLabels = (l for l in $scope.labels when l.id != $scope.labelId)
    $scope.groups = $window.contextData.groups

  $scope.deleteLabel = () ->
    $scope.showConfirm 'Delete this label?', true, () ->
      alert('TODO: delete label')

  #----------------------------------------------------------------------------
  # Support functions
  #----------------------------------------------------------------------------

  $scope.showConfirm = (prompt, danger, callback) ->
    resolve = {prompt: (() -> prompt), danger: (() -> danger)}
    $modal.open({templateUrl: 'confirmModal.html', controller: 'ConfirmModalController', resolve: resolve})
    .result.then () ->
      callback()
]

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

  $scope.init = () ->
    $scope.loadOldMessages()

  #----------------------------------------------------------------------------
  # Message fetching
  #----------------------------------------------------------------------------

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

  #----------------------------------------------------------------------------
  # Selection controls
  #----------------------------------------------------------------------------

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

  #----------------------------------------------------------------------------
  # Selection actions
  #----------------------------------------------------------------------------

  $scope.labelSelection = (label) ->
    $scope.showConfirm 'Apply the label <strong>' + label + '</strong> to the selected messages?', false, () ->
      MessageService.labelMessages($scope.selection, label)

  $scope.flagSelection = () ->
    $scope.showConfirm 'Flag the selected messages?', false, () ->
      MessageService.flagMessages($scope.selection, true)

  $scope.caseForSelection = () ->
    $modal.open({templateUrl: 'openCaseModal.html', controller: 'OpenCaseModalController', resolve: {partners: () -> $scope.partners}})
    .result.then (partner) ->
      alert("TODO: open case assigned to " + partner + " for: " + $scope.selection)

  $scope.replyToSelection = () ->
    $modal.open({templateUrl: 'replyModal.html', controller: 'ReplyModalController', resolve: {}})
    .result.then (message) ->
      alert("TODO: reply with '" + message + "' to: " + $scope.selection)

  $scope.forwardSelection = () ->
    original = $scope.selection[0].text

    $modal.open({templateUrl: 'forwardModal.html', controller: 'ForwardModalController', resolve: {original: () -> original}})
    .result.then (data) ->
      alert("TODO: forward '" + data.message + "' to: " + data.recipient)

  $scope.archiveSelection = () ->
    $scope.showConfirm 'Archive the selected messages? This will remove them from the inbox.', false, () ->
      MessageService.archiveMessages($scope.selection)

  $scope.toggleMessageFlag = (message) ->
    prevState = message.flagged
    message.flagged = !prevState
    MessageService.flagMessages([message], message.flagged)
]


#============================================================================
# Modal dialog controllers
#============================================================================

controllers.controller 'ConfirmModalController', [ '$scope', '$modalInstance', 'prompt', 'danger', ($scope, $modalInstance, prompt, danger) ->
  $scope.prompt = prompt
  $scope.danger = danger
  $scope.ok = () -> $modalInstance.close(true)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]

controllers.controller 'ReplyModalController', [ '$scope', '$modalInstance', ($scope, $modalInstance) ->
  $scope.message = ''
  $scope.ok = () -> $modalInstance.close($scope.message)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]

controllers.controller 'ForwardModalController', [ '$scope', '$modalInstance', 'original', ($scope, $modalInstance, original) ->
  $scope.recipient = ''
  $scope.message = '"' + original + '"'
  $scope.ok = () -> $modalInstance.close({message: $scope.message, recipient: $scope.recipient})
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]

controllers.controller 'OpenCaseModalController', [ '$scope', '$modalInstance', 'partners', ($scope, $modalInstance, partners) ->
  $scope.partners = partners
  $scope.selectedPartner = partners[0]
  $scope.ok = () -> $modalInstance.close($scope.selectedPartner)
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