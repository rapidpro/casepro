controllers = angular.module('upartners.controllers', ['upartners.services']);


URN_SCHEMES = {tel: "Phone", twitter: "Twitter"}

#============================================================================
# Inbox controller
#============================================================================

controllers.controller 'InboxController', [ '$scope', '$window', 'LabelService', 'UtilsService', ($scope, $window, LabelService, UtilsService) ->

  $scope.init = (initialLabelId) ->
    $scope.partners = $window.contextData.partners
    $scope.labels = $window.contextData.labels
    $scope.groups = $window.contextData.groups

    # find and activate initial label
    initialLabel = null
    for l in $scope.labels
        if l.id == initialLabelId
          initialLabel = l
          break
    $scope.activateLabel initialLabel

  $scope.activateLabel = (label) ->
    $scope.activeLabel = label
    if label
      $scope.inactiveLabels = (l for l in $scope.labels when l.id != label.id)
    else
      $scope.inactiveLabels = $scope.labels

    $scope.$broadcast('activeLabelChange')

  $scope.onDeleteLabel = () ->
    UtilsService.showConfirm 'Delete the label <strong>' + $scope.activeLabel.name + '</strong>?', true, () ->
      LabelService.deleteLabel $scope.activeLabel, () ->
        $scope.labels = (l for l in $scope.labels when l.id != $scope.activeLabel.id)
        $scope.activateLabel(null)
        UtilsService.displayAlert('success', 'Label was deleted')
]

#============================================================================
# Messages controller
#============================================================================

controllers.controller 'MessagesController', [ '$scope', '$modal', 'MessageService', 'UtilsService', ($scope, $modal, MessageService, UtilsService) ->

  $scope.messages = []
  $scope.selection = []
  $scope.loadingOld = false
  $scope.hasOlder = true
  $scope.search = { text: null, groups: [], after: null, before: null, reverse: false }
  $scope.activeSearch = {}
  $scope.page = 0
  $scope.totalMessages = 0

  $scope.init = () ->
    $scope.$on 'activeLabelChange', () ->
      $scope.onClearSearch()

    $scope.onClearSearch()

  #----------------------------------------------------------------------------
  # Message searching and fetching
  #----------------------------------------------------------------------------

  $scope.onClearSearch = () ->
    $scope.search = { text: null, groups: [], after: null, before: null, reverse: false }
    $scope.onMessageSearch()

  $scope.onMessageSearch = () ->
    $scope.activeSearch = $scope.search
    $scope.page = 0
    $scope.loadOldMessages()

  $scope.loadOldMessages = ->
    $scope.loadingOld = true
    $scope.page += 1

    MessageService.fetchOldMessages $scope.activeLabel, $scope.page, $scope.search, (messages, total, hasOlder) ->
      if $scope.page == 1
        $scope.messages = messages
      else
        $scope.messages = $scope.messages.concat messages

      $scope.hasOlder = hasOlder
      $scope.totalMessages = total
      $scope.loadingOld = false

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
    UtilsService.showConfirm 'Apply the label <strong>' + label + '</strong> to the selected messages?', false, () ->
      MessageService.labelMessages $scope.selection, label

  $scope.flagSelection = () ->
    UtilsService.showConfirm 'Flag the selected messages?', false, () ->
      MessageService.flagMessages $scope.selection, true

  $scope.caseForSelection = () ->
    $modal.open({templateUrl: 'openCaseModal.html', controller: 'OpenCaseModalController', resolve: {partners: () -> $scope.partners}})
    .result.then (assignee) ->
      alert("TODO: open case assigned to " + assignee + " for: " + $scope.selection)

  $scope.replyToSelection = () ->
    $modal.open({templateUrl: 'replyModal.html', controller: 'ReplyModalController', resolve: {}})
    .result.then (text) ->
      MessageService.replyToMessages $scope.selection, text, () ->
        UtilsService.displayAlert 'success', 'Reply sent to contacts'

  $scope.forwardSelection = () ->
    initialText = '"' + $scope.selection[0].text + '"'

    $modal.open({templateUrl: 'composeModal.html', controller: 'ComposeModalController', resolve: {
      title: () -> "Forward",
      initialText: () -> initialText
    }})
    .result.then (data) ->
      MessageService.sendNewMessage data.urn, data.text, () ->
        UtilsService.displayAlert 'success', 'Message forwarded to ' + data.urn.path

  $scope.archiveSelection = () ->
    UtilsService.showConfirm 'Archive the selected messages? This will remove them from the inbox.', false, () ->
      MessageService.archiveMessages $scope.selection

  #----------------------------------------------------------------------------
  # Other
  #----------------------------------------------------------------------------

  $scope.toggleMessageFlag = (message) ->
    prevState = message.flagged
    message.flagged = !prevState
    MessageService.flagMessages([message], message.flagged)

  $scope.filterDisplayLabels = (labels) ->
    # filters out the active label from the given set of message labels
    if $scope.activeLabel then (l for l in labels when l.id != $scope.activeLabel.id) else labels
]


#============================================================================
# Case controller
#============================================================================

controllers.controller 'CaseController', [ '$scope', '$modal', '$window', 'CaseService', 'UtilsService', ($scope, $modal, $window, CaseService, UtilsService) ->

  $scope.init = (caseId) ->
    $scope.caseId = caseId

  $scope.reassignCase = () ->
    alert('TODO')

  $scope.closeCase = () ->
    UtilsService.showConfirm 'Close this case?', true, () ->
      CaseService.closeCase $scope.caseId, () ->
        $window.location.href = '/case/'
]


#============================================================================
# Case timeline controller
#============================================================================

controllers.controller 'CaseTimelineController', [ '$scope', 'CaseService', ($scope, CaseService) ->

  $scope.timeline = []

  $scope.init = () ->
    $scope.update()

  $scope.update = () ->
    CaseService.fetchTimeline $scope.caseId, null, (events) ->
      $scope.timeline = events

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
  $scope.text = ''
  $scope.ok = () -> $modalInstance.close($scope.text)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]

controllers.controller 'ComposeModalController', [ '$scope', '$modalInstance', 'title', 'initialText', ($scope, $modalInstance, title, initialText) ->
  $scope.title = title
  $scope.urn_scheme = null
  $scope.urn_path = ''
  $scope.text = initialText

  $scope.setScheme = (scheme) ->
    $scope.urn_scheme = scheme
    $scope.urn_scheme_label = URN_SCHEMES[scheme]

  $scope.ok = () ->
    urn = {scheme: $scope.urn_scheme, path: $scope.urn_path, urn: ($scope.urn_scheme + ':' + $scope.urn_path)}
    $modalInstance.close({text: $scope.text, urn: urn})

  $scope.cancel = () -> $modalInstance.dismiss('cancel')

  $scope.setScheme('tel')
]

controllers.controller 'OpenCaseModalController', [ '$scope', '$modalInstance', 'partners', ($scope, $modalInstance, partners) ->
  $scope.partners = partners
  $scope.assignee = partners[0]
  $scope.ok = () -> $modalInstance.close($scope.assignee)
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