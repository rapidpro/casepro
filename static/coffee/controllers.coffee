controllers = angular.module('upartners.controllers', ['upartners.services']);


URN_SCHEMES = {tel: "Phone", twitter: "Twitter"}

# Component refresh intervals
INTERVAL_MESSAGES_NEW = 15000
INTERVAL_CASES_NEW = 5000
INTERVAL_CASE_INFO = 5000
INTERVAL_CASE_TIMELINE = 10000

#============================================================================
# Home controller (DOM parent of inbox and cases)
#============================================================================

controllers.controller 'HomeController', [ '$scope', '$window', '$location', 'LabelService', 'UtilsService', ($scope, $window, $location, LabelService, UtilsService) ->

  $scope.user = $window.contextData.user
  $scope.partners = $window.contextData.partners
  $scope.labels = $window.contextData.labels
  $scope.groups = $window.contextData.groups

  $scope.activeLabel = null
  $scope.activeContact = null

  $scope.init = () ->
    $scope.$on '$locationChangeSuccess', () ->
      params = $location.search()
      initialLabel = null
      if 'label' of params
        for l in $scope.labels
            if l.name == params.label
              initialLabel = l
              break

      $scope.activateLabel(initialLabel)

  $scope.activateLabel = (label) ->
    $scope.activeLabel = label
    $scope.activeContact = null

    if label
      $scope.inactiveLabels = (l for l in $scope.labels when l.id != label.id)
    else
      $scope.inactiveLabels = $scope.labels

    $scope.$broadcast('activeLabelChange')

  $scope.activateContact = (contact) ->
    $scope.activeLabel = null
    $scope.activeContact = contact

    $scope.$broadcast('activeContactChange')

  $scope.onDeleteLabel = () ->
    UtilsService.confirmModal 'Delete the label <strong>' + $scope.activeLabel.name + '</strong>?', 'danger', () ->
      LabelService.deleteLabel $scope.activeLabel, () ->
        $scope.labels = (l for l in $scope.labels when l.id != $scope.activeLabel.id)
        $scope.activateLabel(null)
        UtilsService.displayAlert('success', "Label was deleted")

  $scope.filterDisplayLabels = (labels) ->
    # filters out the active label from the given set of message labels
    if $scope.activeLabel then (l for l in labels when l.id != $scope.activeLabel.id) else labels
]


#============================================================================
# Base controller class for CasesController and MessagesController
#============================================================================

controllers.controller('BaseItemsController', [ '$scope', ($scope) ->

  $scope.items = []
  $scope.startTime = new Date()
  $scope.oldItemsLoading = false
  $scope.oldItemsPage = 0
  $scope.oldItemsMore = false
  $scope.oldItemsTotal = 0
  $scope.newItemsMaxTime = null
  $scope.newItemsCount = 0
  $scope.selection = []

  $scope.totalItems = () -> $scope.oldItemsTotal + $scope.newItemsCount

  #----------------------------------------------------------------------------
  # Search for items based on current search form values
  #----------------------------------------------------------------------------
  $scope.onSearch = () ->
    $scope.activeSearch = $scope.buildSearch()

    $scope.items = []
    $scope.oldItemsPage = 0
    $scope.loadOldItems()

  #----------------------------------------------------------------------------
  # Reset search form and refresh items accordingly
  #----------------------------------------------------------------------------
  $scope.onResetSearch = () ->
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.onSearch()

  #----------------------------------------------------------------------------
  # Selection controls
  #----------------------------------------------------------------------------

  $scope.onSelectAll = () ->
    for item in $scope.items
      item.selected = true
    $scope.onChangeSelection()

  $scope.onSelectNone = () ->
    for item in $scope.items
      item.selected = false
    $scope.selection = []

  $scope.onChangeSelection = () ->
    $scope.selection = (item for item in $scope.items when item.selected)
])


#============================================================================
# Messages controller
#============================================================================

controllers.controller 'MessagesController', [ '$scope', '$timeout', '$modal', '$controller', 'MessageService', 'CaseService', 'UtilsService', ($scope, $timeout, $modal, $controller, MessageService, CaseService, UtilsService) ->
  $controller('BaseItemsController', {$scope: $scope})

  $scope.expandedMessageId = null

  $scope.init = (msgType) ->
    $scope.msgType = msgType
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.activeSearch = $scope.buildSearch()

    $scope.refreshNewItems()

    $scope.$on 'activeLabelChange', () ->
      $scope.onResetSearch()
    $scope.$on 'activeContactChange', () ->
      $scope.onResetSearch()

  $scope.buildSearch = () ->
    search = angular.copy($scope.searchFields)
    search.archived = $scope.msgType == 'archived'
    search.label = $scope.activeLabel
    search.contact = $scope.activeContact
    search.timeCode = Date.now()
    return search

  $scope.searchFieldDefaults = () -> { text: null, groups: [], after: null, before: null }

  $scope.onExportSearch = () ->
    UtilsService.confirmModal "Export the current message search?", null, () ->
      MessageService.startExport $scope.activeSearch, () ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")

  $scope.loadOldItems = () ->
    $scope.oldItemsLoading = true
    $scope.oldItemsPage += 1

    MessageService.fetchOld $scope.activeSearch, $scope.startTime, $scope.oldItemsPage, (messages, total, hasMore) ->
      $scope.items = $scope.items.concat(messages)
      $scope.oldItemsMore = hasMore
      $scope.oldItemsTotal = total
      $scope.oldItemsLoading = false

  $scope.refreshNewItems = () ->
    # if user has specified a max time then don't bother looking for new messages
    if $scope.activeSearch.before
      $timeout($scope.refreshNewItems, INTERVAL_MESSAGES_NEW)
      return

    timeCode = $scope.activeSearch.timeCode
    afterTime = $scope.newItemsMaxTime or $scope.startTime
    $scope.newItemsMaxTime = new Date()

    MessageService.fetchNew $scope.activeSearch, afterTime, $scope.newItemsMaxTime, (cases) ->
      if timeCode == $scope.activeSearch.timeCode
        $scope.items = cases.concat($scope.items)
        $scope.newItemsCount += cases.length

      $timeout($scope.refreshNewItems, INTERVAL_MESSAGES_NEW)

  $scope.onExpandMessage = (message) ->
    $scope.expandedMessageId = message.id

  #----------------------------------------------------------------------------
  # Selection actions
  #----------------------------------------------------------------------------

  $scope.labelSelection = (label) ->
    UtilsService.confirmModal 'Apply the label <strong>' + label.name + '</strong> to the selected messages?', null, () ->
      MessageService.labelMessages($scope.selection, label)

  $scope.flagSelection = () ->
    UtilsService.confirmModal 'Flag the selected messages?', null, () ->
      MessageService.flagMessages($scope.selection, true)

  $scope.replyToSelection = () ->
    $modal.open({templateUrl: 'replyModal.html', controller: 'ReplyModalController', resolve: {}})
    .result.then((text) ->
      MessageService.replyToMessages($scope.selection, text, () ->
        MessageService.archiveMessages($scope.selection, () ->
          UtilsService.displayAlert('success', "Reply sent and messages archived")
        )
      )
    )

  $scope.archiveSelection = () ->
    UtilsService.confirmModal 'Archive the selected messages? This will remove them from your inbox.', null, () ->
      MessageService.archiveMessages($scope.selection, ()->)

  #----------------------------------------------------------------------------
  # Single message actions
  #----------------------------------------------------------------------------

  $scope.onToggleMessageFlag = (message) ->
    prevState = message.flagged
    message.flagged = !prevState
    MessageService.flagMessages([message], message.flagged)

  $scope.onForwardMessage = (message) ->
    initialText = '"' + message.text + '"'

    $modal.open({templateUrl: 'composeModal.html', controller: 'ComposeModalController', resolve: {
      title: () -> "Forward",
      initialText: () -> initialText
    }})
    .result.then (data) ->
      MessageService.sendNewMessage data.urn, data.text, () ->
        UtilsService.displayAlert('success', "Message forwarded to " + data.urn.path)

  $scope.onCaseFromMessage = (message) ->
    openCase = (assignee) ->
      CaseService.openCase message, assignee, (_case) ->
          UtilsService.navigate('/case/read/' + _case.id + '/')

    prompt = "Open a new case for this message?"
    if $scope.user.partner
      UtilsService.confirmModal prompt, null, () ->
        openCase($scope.user.partner)
    else
      UtilsService.assignModal "New case", prompt, $scope.partners, (assignee) ->
        openCase(assignee)

  $scope.onShowMessageHistory = (message) ->
    $modal.open({templateUrl: 'messageHistory.html', controller: 'MessageHistoryModalController', resolve: {
      message: () -> message
    }})
]


#============================================================================
# Cases listing controller
#============================================================================

controllers.controller('CasesController', [ '$scope', '$timeout', '$controller', 'CaseService', 'UtilsService', ($scope, $timeout, $controller, CaseService, UtilsService) ->
  $controller('BaseItemsController', {$scope: $scope})

  $scope.init = (caseStatus) ->
    $scope.caseStatus = caseStatus
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.activeSearch = $scope.buildSearch()

    $scope.refreshNewItems()

    $scope.$on 'activeLabelChange', () ->
      $scope.onResetSearch()

  $scope.buildSearch = () ->
    search = angular.copy($scope.searchFields)
    search.label = $scope.activeLabel
    search.status = $scope.caseStatus
    search.timeCode = Date.now()
    return search

  $scope.searchFieldDefaults = () -> { assignee: null }

  $scope.loadOldItems = () ->
    $scope.oldItemsLoading = true
    $scope.oldItemsPage += 1

    CaseService.fetchOld $scope.activeSearch, $scope.startTime, $scope.oldItemsPage, (cases, total, hasMore) ->
      $scope.items = $scope.items.concat(cases)
      $scope.oldItemsMore = hasMore
      $scope.oldItemsTotal = total
      $scope.oldItemsLoading = false

  $scope.refreshNewItems = () ->
    timeCode = $scope.activeSearch.timeCode
    afterTime = $scope.newItemsMaxTime or $scope.startTime
    $scope.newItemsMaxTime = new Date()

    CaseService.fetchNew $scope.activeSearch, afterTime, $scope.newItemsMaxTime, (cases) ->
      if timeCode == $scope.activeSearch.timeCode
        $scope.items = cases.concat($scope.items)
        $scope.newItemsCount += cases.length

      $timeout($scope.refreshNewItems, INTERVAL_CASES_NEW)

  $scope.closeSelection = () ->
    UtilsService.confirmModal 'Close the selected cases?', 'danger', () ->
      CaseService.closeCases($scope.selection)

])


#============================================================================
# Case view controller
#============================================================================

controllers.controller 'CaseController', [ '$scope', '$window', '$timeout', 'CaseService', 'MessageService', 'UtilsService', ($scope, $window, $timeout, CaseService, MessageService, UtilsService) ->

  $scope.case = $window.contextData.case
  $scope.contact = $window.contextData.contact
  $scope.allPartners = $window.contextData.all_partners
  $scope.allLabels = $window.contextData.all_labels

  $scope.newMessage = ''
  $scope.sending = false

  $scope.init = (maxMsgChars) ->
    $scope.msgCharsRemaining = $scope.maxMsgChars = maxMsgChars

    $scope.refresh()

  $scope.refresh = () ->
    CaseService.fetchCase $scope.case.id, (_case) ->
      $scope.case = _case
      $timeout($scope.refresh, INTERVAL_CASE_INFO)

  $scope.onEditLabels = ->
    UtilsService.labelModal "Labels", "Update the labels for this case. This determines which other partner organizations can view this case.", $scope.allLabels, $scope.case.labels, (selectedLabels) ->
      CaseService.labelCase $scope.case, selectedLabels, ->

  #----------------------------------------------------------------------------
  # Messaging
  #----------------------------------------------------------------------------

  $scope.sendMessage = ->
    $scope.sending = true

    MessageService.sendNewMessage $scope.contact, $scope.newMessage, ->
      $scope.newMessage = ''
      $scope.sending = false

  $scope.onNewMessageChanged = ->
    $scope.msgCharsRemaining = $scope.maxMsgChars - $scope.newMessage.length

  #----------------------------------------------------------------------------
  # Case actions
  #----------------------------------------------------------------------------

  $scope.note = () ->
    UtilsService.noteModal "Add Note", null, null, (note) ->
      CaseService.noteCase $scope.case, note, () ->
        $scope.$broadcast('newCaseAction')

  $scope.reassign = () ->
    UtilsService.assignModal "Re-assign", null, $scope.allPartners, (assignee) ->
      CaseService.reassignCase $scope.case, assignee, () ->
        $scope.$broadcast('newCaseAction')

  $scope.close = () ->
    UtilsService.noteModal "Close", "Close this case?", 'danger', (note) ->
      CaseService.closeCase $scope.case, note, () ->
        UtilsService.navigate('/')

  $scope.reopen = () ->
    UtilsService.noteModal "Re-open", "Re-open this case?", null, (note) ->
      CaseService.reopenCase $scope.case, note, () ->
        $scope.$broadcast('newCaseAction')
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
        $timeout((() -> $scope.update(true)), INTERVAL_CASE_TIMELINE)
]


#============================================================================
# Modal dialog controllers
#============================================================================

controllers.controller 'ConfirmModalController', [ '$scope', '$modalInstance', 'prompt', 'style', ($scope, $modalInstance, prompt, style) ->
  $scope.title = "Confirm"
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

controllers.controller('LabelModalController', ['$scope', '$modalInstance', 'title', 'prompt', 'labels', 'initial', ($scope, $modalInstance, title, prompt, labels, initial) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.selection = ({label: l, selected: (l.id in (i.id for i in initial))} for l in labels)

  $scope.ok = () ->
    selectedLabels = (item.label for item in $scope.selection when item.selected)
    $modalInstance.close(selectedLabels)

  $scope.cancel = () -> $modalInstance.dismiss('cancel')
])

controllers.controller('ReplyModalController', [ '$scope', '$modalInstance', ($scope, $modalInstance) ->
  $scope.text = ''

  $scope.ok = () -> $modalInstance.close($scope.text)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
])

controllers.controller('ComposeModalController', ['$scope', '$modalInstance', 'title', 'initialText', ($scope, $modalInstance, title, initialText) ->
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
])

controllers.controller('MessageHistoryModalController', ['$scope', '$modalInstance', 'MessageService', 'message', ($scope, $modalInstance, MessageService, message) ->
  $scope.message = message
  $scope.loading = true

  MessageService.fetchHistory($scope.message, (actions)->
    $scope.actions = actions
    $scope.loading = false
  )

  $scope.close = () -> $modalInstance.dismiss('close')
])


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