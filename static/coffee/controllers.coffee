controllers = angular.module('upartners.controllers', ['upartners.services']);


URN_SCHEMES = {tel: "Phone", twitter: "Twitter"}

# Component refresh intervals
INTERVAL_CASE_INFO = 5000
INTERVAL_CASE_TIMELINE = 10000

#============================================================================
# Inbox controller
#============================================================================

controllers.controller 'InboxController', [ '$scope', '$window', 'LabelService', 'UtilsService', ($scope, $window, LabelService, UtilsService) ->

  $scope.userPartner = $window.contextData.user_partner
  $scope.partners = $window.contextData.partners
  $scope.labels = $window.contextData.labels
  $scope.groups = $window.contextData.groups

  $scope.init = (initialLabelId) ->
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
    UtilsService.confirmModal 'Delete the label <strong>' + $scope.activeLabel.name + '</strong>?', 'danger', () ->
      LabelService.deleteLabel $scope.activeLabel, () ->
        $scope.labels = (l for l in $scope.labels when l.id != $scope.activeLabel.id)
        $scope.activateLabel(null)
        UtilsService.displayAlert 'success', "Label was deleted"
]

#============================================================================
# Messages controller
#============================================================================

controllers.controller 'MessagesController', [ '$scope', '$modal', 'MessageService', 'CaseService', 'UtilsService', ($scope, $modal, MessageService, CaseService, UtilsService) ->

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
    $scope.activeSearch = angular.copy($scope.search)
    $scope.page = 0
    $scope.loadOldMessages()

  $scope.loadOldMessages = ->
    $scope.loadingOld = true
    $scope.page += 1

    MessageService.fetchOldMessages $scope.activeLabel, $scope.page, $scope.activeSearch, (messages, total, hasOlder) ->
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
    UtilsService.confirmModal 'Apply the label <strong>' + label + '</strong> to the selected messages?', null, () ->
      MessageService.labelMessages $scope.selection, label

  $scope.flagSelection = () ->
    UtilsService.confirmModal 'Flag the selected messages?', null, () ->
      MessageService.flagMessages $scope.selection, true

  $scope.caseForSelection = () ->
    openCase = (assignee) ->
      CaseService.openCase $scope.selection[0], assignee, (_case) ->
          UtilsService.navigate '/case/read/' + _case.id + '/'

    prompt = "Open a new case for the selected message?"
    if $scope.userPartner
      UtilsService.confirmModal prompt, null, () ->
        openCase $scope.userPartner
    else
      UtilsService.assignModal "New case", prompt, $scope.partners, (assignee) ->
        openCase assignee

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
    UtilsService.confirmModal 'Archive the selected messages? This will remove them from the inbox.', null, () ->
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

controllers.controller 'CaseController', [ '$scope', '$window', '$timeout', 'CaseService', 'UtilsService', ($scope, $window, $timeout, CaseService, UtilsService) ->

  $scope.case = $window.contextData.case
  $scope.partners = $window.contextData.partners

  $scope.init = () ->
    $scope.refresh()

  $scope.refresh = () ->
    CaseService.fetchCase $scope.case.id, (_case) ->
      $scope.case = _case
      $timeout $scope.refresh, INTERVAL_CASE_INFO

  $scope.note = () ->
    UtilsService.noteModal "Add Note", null, null, (note) ->
      CaseService.noteCase $scope.case, note, () ->
        $scope.$broadcast 'newCaseAction'

  $scope.reassign = () ->
    UtilsService.assignModal "Re-assign", null, $scope.partners, (assignee) ->
      CaseService.reassignCase $scope.case, assignee, () ->
        $scope.$broadcast 'newCaseAction'

  $scope.close = () ->
    UtilsService.noteModal "Close", "Close this case?", 'danger', (note) ->
      CaseService.closeCase $scope.case, note, () ->
        UtilsService.navigate '/case/'

  $scope.reopen = () ->
    UtilsService.noteModal "Re-open", "Re-open this case?", null, (note) ->
      CaseService.reopenCase $scope.case, note, () ->
        $scope.$broadcast 'newCaseAction'
]


#============================================================================
# Case timeline controller
#============================================================================

controllers.controller 'CaseTimelineController', [ '$scope', '$timeout', 'CaseService', ($scope, $timeout, CaseService) ->

  $scope.timeline = []
  $scope.lastEventTime = null
  $scope.lastActionId = null
  $scope.lastMessageId = null

  $scope.init = () ->
    $scope.$on 'newCaseAction', () ->
      $scope.update(false)

    $scope.update(true)

  $scope.update = (repeat) ->
    CaseService.fetchTimeline $scope.case, $scope.lastEventTime, $scope.lastMessageId, $scope.lastActionId, (events, lastEventTime, lastMessageId, lastActionId) ->
      $scope.timeline = $scope.timeline.concat events
      $scope.lastEventTime = lastEventTime
      $scope.lastMessageId = lastMessageId
      $scope.lastActionId = lastActionId

      if repeat
        $timeout (() -> $scope.update(true)), INTERVAL_CASE_TIMELINE
]


#============================================================================
# Modal dialog controllers
#============================================================================

controllers.controller 'ConfirmModalController', [ '$scope', '$modalInstance', 'prompt', 'style', ($scope, $modalInstance, prompt, style) ->
  $scope.prompt = prompt
  $scope.style = style or 'primary'

  $scope.ok = () -> $modalInstance.close(true)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]

controllers.controller 'AssignModalController', [ '$scope', '$modalInstance', 'title', 'prompt', 'partners', ($scope, $modalInstance, title, prompt, partners) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.partners = partners
  $scope.assignee = partners[0]

  $scope.ok = () -> $modalInstance.close($scope.assignee)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]

controllers.controller 'NoteModalController', [ '$scope', '$modalInstance', 'title', 'prompt', 'style', ($scope, $modalInstance, title, prompt, style) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.style = style or 'primary'
  $scope.note = ''

  $scope.ok = () -> $modalInstance.close($scope.note)
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