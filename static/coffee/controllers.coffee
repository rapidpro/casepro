#============================================================================
# Component controllers
#============================================================================

controllers = angular.module('cases.controllers', ['cases.services', 'cases.modals']);


# Component refresh intervals
INTERVAL_MESSAGES_NEW = 15000
INTERVAL_CASES_NEW = 5000
INTERVAL_CASE_INFO = 5000
INTERVAL_CASE_TIMELINE = 10000

SELECT_ALL_FETCH_SIZE = 1000

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

  $scope.init = (itemView) ->
    $scope.itemView = itemView

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

  #----------------------------------------------------------------------------
  # Total number of items that match current view and search
  #----------------------------------------------------------------------------
  $scope.totalItems = () ->
    # need to discount the number of items which are being filtered out
    filter = $scope.getItemFilter()
    numHidden = 0
    for item in $scope.items
      if !filter(item)
        numHidden += 1

    $scope.oldItemsTotal + $scope.newItemsCount - numHidden

  #----------------------------------------------------------------------------
  # Search for items based on current search form values
  #----------------------------------------------------------------------------
  $scope.onSearch = () ->
    $scope.activeSearch = $scope.buildSearch()

    $scope.items = []
    $scope.oldItemsPage = 0
    $scope.loadOldItems(false)

  #----------------------------------------------------------------------------
  # Reset search form and refresh items accordingly
  #----------------------------------------------------------------------------
  $scope.onResetSearch = () ->
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.onSearch()

  #----------------------------------------------------------------------------
  # User selects all items
  #----------------------------------------------------------------------------
  $scope.onSelectAll = () ->
    # select all loaded items
    for item in $scope.items
      item.selected = true
    $scope.updateSelection()

    # load and select more items if there are more
    if $scope.oldItemsMore and $scope.totalItems() < SELECT_ALL_FETCH_SIZE
      $scope.loadOldItems(true)

  #----------------------------------------------------------------------------
  # User selects no items
  #----------------------------------------------------------------------------
  $scope.onSelectNone = () ->
    for item in $scope.items
      item.selected = false
    $scope.selection = []

  #----------------------------------------------------------------------------
  # User selects or deselects an item
  #----------------------------------------------------------------------------
  $scope.onChangeSelection = () ->
    $scope.updateSelection()

  #----------------------------------------------------------------------------
  # Selection has changed
  #----------------------------------------------------------------------------
  $scope.updateSelection = () ->
    filter = $scope.getItemFilter()
    $scope.selection = (item for item in $scope.items when item.selected and filter(item))

  #----------------------------------------------------------------------------
  # Load old items due to scroll down or select all
  #----------------------------------------------------------------------------
  $scope.loadOldItems = (forSelectAll) ->
    $scope.oldItemsLoading = true
    $scope.oldItemsPage += 1

    $scope.fetchOldItems (items, total, hasMore) ->
      $scope.items = $scope.items.concat(items)
      $scope.oldItemsMore = hasMore
      $scope.oldItemsTotal = total
      $scope.oldItemsLoading = false

      if forSelectAll
        for item in items
          item.selected = true
        $scope.updateSelection()
        if $scope.oldItemsMore and $scope.totalItems() < SELECT_ALL_FETCH_SIZE
          $scope.loadOldItems(true)
])


#============================================================================
# Messages controller
#============================================================================
controllers.controller 'MessagesController', [ '$scope', '$timeout', '$modal', '$controller', 'MessageService', 'CaseService', 'UtilsService', ($scope, $timeout, $modal, $controller, MessageService, CaseService, UtilsService) ->
  $controller('BaseItemsController', {$scope: $scope})

  $scope.advancedSearch = false
  $scope.expandedMessageId = null

  $scope.init = () ->
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.activeSearch = $scope.buildSearch()

    $scope.refreshNewItems()

    $scope.$on 'activeLabelChange', () ->
      $scope.onResetSearch()
      $scope.setAdvancedSearch(false)
    $scope.$on 'activeContactChange', () ->
      $scope.onResetSearch()
      $scope.setAdvancedSearch(false)

  $scope.getItemFilter = () ->
    if $scope.itemView == 'inbox'
      return (item) -> !item.archived
    else if $scope.itemView == 'flagged'
      return (item) -> !item.archived and item.flagged
    else if $scope.itemView == 'archived'
      return (item) -> item.archived

  $scope.buildSearch = () ->
    search = angular.copy($scope.searchFields)
    search.view = $scope.itemView
    search.label = $scope.activeLabel
    search.contact = $scope.activeContact
    search.timeCode = Date.now()
    return search

  $scope.searchFieldDefaults = () -> { text: null, groups: [], after: null, before: null }

  $scope.setAdvancedSearch = (state) ->
    $scope.advancedSearch = state

  $scope.onExportSearch = () ->
    UtilsService.confirmModal "Export the current message search?", null, () ->
      MessageService.startExport $scope.activeSearch, () ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")

  $scope.fetchOldItems = (callback) ->
    MessageService.fetchOld $scope.activeSearch, $scope.startTime, $scope.oldItemsPage, callback

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

  $scope.onLabelSelection = (label) ->
    UtilsService.confirmModal 'Apply the label <strong>' + label.name + '</strong> to the selected messages?', null, () ->
      MessageService.labelMessages($scope.selection, label, () ->
        $scope.updateSelection()
      )

  $scope.onFlagSelection = () ->
    UtilsService.confirmModal 'Flag the selected messages?', null, () ->
      MessageService.flagMessages($scope.selection, true, () ->
        $scope.updateSelection()
      )

  $scope.onReplyToSelection = () ->
    $modal.open({templateUrl: 'replyModal.html', controller: 'ReplyModalController', resolve: {}})
    .result.then((text) ->
      MessageService.replyToMessages($scope.selection, text, () ->
        MessageService.archiveMessages($scope.selection, () ->
          UtilsService.displayAlert('success', "Reply sent and messages archived")
          $scope.updateSelection()
        )
      )
    )

  $scope.onArchiveSelection = () ->
    UtilsService.confirmModal('Archive the selected messages? This will remove them from your inbox.', null, () ->
      MessageService.archiveMessages($scope.selection, () ->
        $scope.updateSelection()
      )
    )

  $scope.onRestoreSelection = () ->
    UtilsService.confirmModal('Restore the selected messages? This will put them back in your inbox.', null, () ->
      MessageService.restoreMessages($scope.selection, () ->
        $scope.updateSelection()
      )
    )

  #----------------------------------------------------------------------------
  # Single message actions
  #----------------------------------------------------------------------------

  $scope.onToggleMessageFlag = (message) ->
    prevState = message.flagged
    message.flagged = !prevState
    MessageService.flagMessages([message], message.flagged, () ->
      $scope.updateSelection()
    )

  $scope.onForwardMessage = (message) ->
    initialText = '"' + message.text + '"'

    $modal.open({templateUrl: 'composeModal.html', controller: 'ComposeModalController', resolve: {
      title: () -> "Forward",
      initialText: () -> initialText
    }})
    .result.then((data) ->
      MessageService.forwardToUrn(data.text, data.urn, () ->
        UtilsService.displayAlert('success', "Message forwarded to " + data.urn.path)
      )
    )

  $scope.onCaseFromMessage = (message) ->
    partners = if $scope.user.partner then null else $scope.partners
    resolve = {message: (() -> message), partners: (() -> partners)}
    $modal.open({templateUrl: 'newCaseModal.html', controller: 'NewCaseModalController', resolve: resolve})
    .result.then (result) ->
      CaseService.openCase(message, result.summary, result.assignee, (_case) ->
          UtilsService.navigate('/case/read/' + _case.id + '/')
      )

  $scope.onLabelMessage = (message) ->
    UtilsService.labelModal "Labels", "Update the labels for this message. This determines which other partner organizations can view this message.", $scope.labels, message.labels, (selectedLabels) ->
      MessageService.relabelMessage(message, selectedLabels, () ->
        $scope.updateSelection()
      )

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

  $scope.init = () ->
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.activeSearch = $scope.buildSearch()

    $scope.refreshNewItems()

    $scope.$on 'activeLabelChange', () ->
      $scope.onResetSearch()

  $scope.getItemFilter = () ->
    if $scope.itemView == 'open'
      return (item) -> !item.is_closed
    else if $scope.itemView == 'closed'
      return (item) -> item.is_closed

  $scope.buildSearch = () ->
    search = angular.copy($scope.searchFields)
    search.view = $scope.itemView
    search.label = $scope.activeLabel
    search.timeCode = Date.now()
    return search

  $scope.searchFieldDefaults = () -> { assignee: $scope.user.partner }

  $scope.fetchOldItems = (callback) ->
    CaseService.fetchOld $scope.activeSearch, $scope.startTime, $scope.oldItemsPage, callback

  $scope.refreshNewItems = () ->
    timeCode = $scope.activeSearch.timeCode
    afterTime = $scope.newItemsMaxTime or $scope.startTime
    $scope.newItemsMaxTime = new Date()

    CaseService.fetchNew($scope.activeSearch, afterTime, $scope.newItemsMaxTime, (cases) ->
      if timeCode == $scope.activeSearch.timeCode
        $scope.items = cases.concat($scope.items)
        $scope.newItemsCount += cases.length

      $timeout($scope.refreshNewItems, INTERVAL_CASES_NEW)
    )

  $scope.onClickCase = (_case) ->
    UtilsService.navigate('/case/read/' + _case.id + '/')
])


#============================================================================
# Case view controller
#============================================================================
controllers.controller 'CaseController', [ '$scope', '$window', '$timeout', 'CaseService', 'MessageService', 'UtilsService', ($scope, $window, $timeout, CaseService, MessageService, UtilsService) ->

  $scope.case = $window.contextData.case
  $scope.allPartners = $window.contextData.all_partners
  $scope.allLabels = $window.contextData.all_labels

  $scope.newMessage = ''
  $scope.sending = false

  $scope.init = (maxMsgChars) ->
    $scope.msgCharsRemaining = $scope.maxMsgChars = maxMsgChars

    $scope.refresh()

  $scope.refresh = () ->
    CaseService.fetchCase($scope.case.id, (_case) ->
      $scope.case = _case
      $timeout($scope.refresh, INTERVAL_CASE_INFO)
    )

  $scope.onEditLabels = ->
    UtilsService.labelModal("Labels", "Update the labels for this case. This determines which other partner organizations can view this case.", $scope.allLabels, $scope.case.labels, (selectedLabels) ->
      CaseService.relabelCase($scope.case, selectedLabels, () ->
        $scope.$broadcast('timelineChanged')
      )
    )

  $scope.onEditSummary = ->
    UtilsService.editModal("Edit Summary", $scope.case.summary, (text) ->
      CaseService.updateCaseSummary($scope.case, text, () ->
        $scope.$broadcast('timelineChanged')
      )
    )

  #----------------------------------------------------------------------------
  # Messaging
  #----------------------------------------------------------------------------

  $scope.sendMessage = ->
    $scope.sending = true

    MessageService.replyInCase($scope.newMessage, $scope.case, () ->
      $scope.newMessage = ''
      $scope.sending = false
      $scope.$broadcast('timelineChanged')
    )

  $scope.onNewMessageChanged = ->
    $scope.msgCharsRemaining = $scope.maxMsgChars - $scope.newMessage.length

  #----------------------------------------------------------------------------
  # Case actions
  #----------------------------------------------------------------------------

  $scope.onAddNote = () ->
    UtilsService.noteModal("Add Note", null, null, (note) ->
      CaseService.noteCase($scope.case, note, () ->
        $scope.$broadcast('timelineChanged')
      )
    )

  $scope.onReassign = () ->
    UtilsService.assignModal("Re-assign", null, $scope.allPartners, (assignee) ->
      CaseService.reassignCase($scope.case, assignee, () ->
        $scope.$broadcast('timelineChanged')
      )
    )

  $scope.onClose = () ->
    UtilsService.noteModal("Close", "Close this case?", 'danger', (note) ->
      CaseService.closeCase($scope.case, note, () ->
        UtilsService.navigate('/')
      )
    )

  $scope.onReopen = () ->
    UtilsService.noteModal("Re-open", "Re-open this case?", null, (note) ->
      CaseService.reopenCase($scope.case, note, () ->
        $scope.$broadcast('timelineChanged')
      )
    )
]


#============================================================================
# Case timeline controller
#============================================================================
controllers.controller 'CaseTimelineController', [ '$scope', '$timeout', 'CaseService', ($scope, $timeout, CaseService) ->

  $scope.timeline = []
  $scope.startTime = new Date()
  $scope.newItemsMaxTime = null

  $scope.init = () ->
    $scope.$on 'timelineChanged', () ->
      $scope.refreshItems(false)

    $scope.refreshItems(true)

  $scope.refreshItems = (repeat) ->
    afterTime = $scope.newItemsMaxTime
    $scope.newItemsMaxTime = new Date()

    CaseService.fetchTimeline($scope.case, afterTime, $scope.newItemsMaxTime, (events) ->
      $scope.timeline = $scope.timeline.concat events

      if repeat
        $timeout((() -> $scope.refreshItems(true)), INTERVAL_CASE_TIMELINE)
    )
]


#============================================================================
# Partner view controller
#============================================================================
controllers.controller 'PartnerController', [ '$scope', '$window', 'UtilsService', 'PartnerService', ($scope, $window, UtilsService, PartnerService) ->

  $scope.partner = $window.contextData.partner

  $scope.onDeletePartner = () ->
    UtilsService.confirmModal("Remove this partner organization", 'danger', () ->
      PartnerService.deletePartner($scope.partner, () ->
        UtilsService.navigate('/partner/')
      )
    )
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