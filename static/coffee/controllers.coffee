#============================================================================
# Component controllers
#============================================================================

controllers = angular.module('cases.controllers', ['cases.services', 'cases.modals']);


# Component refresh intervals
INTERVAL_MESSAGES_NEW = 30000
INTERVAL_CASES_NEW = 30000
INTERVAL_CASE_INFO = 30000
INTERVAL_CASE_TIMELINE = 30000

INFINITE_SCROLL_MAX_ITEMS = 1000

# Form constraints
CASE_SUMMARY_MAX_LEN = 255
CASE_NOTE_MAX_LEN = 1024
OUTGOING_TEXT_MAX_LEN = 480


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

  $scope.init = (folder) ->
    $scope.folder = folder

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
    UtilsService.confirmModal('Delete the label <strong>' + $scope.activeLabel.name + '</strong>?', 'danger', () ->
      LabelService.deleteLabel($scope.activeLabel).then(() ->
        $scope.labels = (l for l in $scope.labels when l.id != $scope.activeLabel.id)
        $scope.activateLabel(null)
        UtilsService.displayAlert('success', "Label was deleted")
      )
    )

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
  $scope.oldItemsMore = true
  $scope.newItemsMaxTime = null
  $scope.selection = []

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
    $scope.updateItems()

    # load and select more items if there are more
    if $scope.oldItemsMore and $scope.items.length < INFINITE_SCROLL_MAX_ITEMS
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
    $scope.updateItems(false)

  #----------------------------------------------------------------------------
  # Items have been changed, so update item list and selection
  #----------------------------------------------------------------------------
  $scope.updateItems = (refilter = true) ->
    filter = $scope.getItemFilter()
    newItems = []
    newSelection = []
    for item in $scope.items
      if not refilter or filter(item)
        newItems.push(item)
        if item.selected
          newSelection.push(item)

    $scope.items = newItems
    $scope.selection = newSelection

  #----------------------------------------------------------------------------
  # Load old items due to scroll down or select all
  #----------------------------------------------------------------------------
  $scope.loadOldItems = (forSelectAll) ->
    $scope.oldItemsLoading = true
    $scope.oldItemsPage += 1

    $scope.fetchOldItems((items, hasMore) ->
      $scope.items = $scope.items.concat(items)
      $scope.oldItemsMore = hasMore
      $scope.oldItemsLoading = false

      if forSelectAll
        for item in items
          item.selected = true
        $scope.updateItems(false)
        if $scope.oldItemsMore and $scope.items.length < INFINITE_SCROLL_MAX_ITEMS
          $scope.loadOldItems(true)
    )

  $scope.isInfiniteScrollEnabled = () ->
    not $scope.oldItemsLoading and $scope.oldItemsMore and $scope.items.length < INFINITE_SCROLL_MAX_ITEMS

  $scope.hasTooManyItemsToDisplay = () ->
    $scope.oldItemsMore and $scope.items.length >= INFINITE_SCROLL_MAX_ITEMS
])


#============================================================================
# Incoming messages controller
#============================================================================
controllers.controller 'MessagesController', [ '$scope', '$timeout', '$uibModal', '$controller', 'MessageService', 'CaseService', 'UtilsService', ($scope, $timeout, $uibModal, $controller, MessageService, CaseService, UtilsService) ->
  $controller('BaseItemsController', {$scope: $scope})

  $scope.advancedSearch = false
  $scope.expandedMessageId = null

  $scope.init = () ->
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.activeSearch = $scope.buildSearch()

    # TODO temporarily disable auto-refresh of new items until refactor is complete
    # $scope.refreshNewItems()

    $scope.$on('activeLabelChange', () ->
      $scope.onResetSearch()
      $scope.setAdvancedSearch(false)
    )
    $scope.$on('activeContactChange', () ->
      $scope.onResetSearch()
      $scope.setAdvancedSearch(false)
    )

  $scope.getItemFilter = () ->
    if $scope.folder == 'inbox'
      return (item) -> !item.archived
    else if $scope.folder == 'flagged'
      return (item) -> (!item.archived or $scope.searchFields.archived) and item.flagged
    else if $scope.folder == 'archived'
      return (item) -> item.archived
    else if $scope.folder == 'unlabelled'
      return (item) -> !item.archived and item.labels.length == 0

  $scope.buildSearch = () ->
    search = angular.copy($scope.searchFields)
    search.folder = $scope.folder
    search.label = $scope.activeLabel
    search.contact = $scope.activeContact
    search.timeCode = Date.now()

    # searching up to a date means including anything on the date
    if search.before
      search.before.setHours(23, 59, 59, 999)

    return search

  $scope.searchFieldDefaults = () -> { text: null, groups: [], after: null, before: null, archived: false }

  $scope.setAdvancedSearch = (state) ->
    $scope.advancedSearch = state

  $scope.onExportSearch = () ->
    UtilsService.confirmModal("Export the current message search?", null, () ->
      MessageService.startExport($scope.activeSearch).then(() ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")
      )
    )

  $scope.fetchOldItems = (callback) ->
    MessageService.fetchOld($scope.activeSearch, $scope.startTime, $scope.oldItemsPage, callback)

  $scope.refreshNewItems = () ->
    # if user has specified a max time then don't bother looking for new messages
    if $scope.activeSearch.before
      $timeout($scope.refreshNewItems, INTERVAL_MESSAGES_NEW)
      return

    timeCode = $scope.activeSearch.timeCode
    afterTime = $scope.newItemsMaxTime or $scope.startTime
    $scope.newItemsMaxTime = new Date()

    MessageService.fetchNew $scope.activeSearch, afterTime, $scope.newItemsMaxTime, (items) ->
      if timeCode == $scope.activeSearch.timeCode
        $scope.items = items.concat($scope.items)

      if items.length < INFINITE_SCROLL_MAX_ITEMS
        $timeout($scope.refreshNewItems, INTERVAL_MESSAGES_NEW)

  $scope.onExpandMessage = (message) ->
    $scope.expandedMessageId = message.id

  #----------------------------------------------------------------------------
  # Selection actions
  #----------------------------------------------------------------------------

  $scope.onLabelSelection = (label) ->
    UtilsService.confirmModal('Apply the label <strong>' + label.name + '</strong> to the selected messages?', null, () ->
      MessageService.labelMessages($scope.selection, label, () ->
        $scope.updateItems()
      )
    )

  $scope.onFlagSelection = () ->
    UtilsService.confirmModal('Flag the selected messages?', null, () ->
      MessageService.flagMessages($scope.selection, true, () ->
        $scope.updateItems()
      )
    )

  $scope.onReplyToSelection = () ->
    $uibModal.open({templateUrl: 'replyModal.html', controller: 'ReplyModalController', resolve: {maxLength: (() -> OUTGOING_TEXT_MAX_LEN)}})
    .result.then((text) ->
      MessageService.replyToMessages($scope.selection, text, () ->
        MessageService.archiveMessages($scope.selection, () ->
          UtilsService.displayAlert('success', "Reply sent and messages archived")
          $scope.updateItems()
        )
      )
    )

  $scope.onArchiveSelection = () ->
    UtilsService.confirmModal('Archive the selected messages? This will remove them from your inbox.', null, () ->
      MessageService.archiveMessages($scope.selection, () ->
        $scope.updateItems()
      )
    )

  $scope.onRestoreSelection = () ->
    UtilsService.confirmModal('Restore the selected messages? This will put them back in your inbox.', null, () ->
      MessageService.restoreMessages($scope.selection, () ->
        $scope.updateItems()
      )
    )

  #----------------------------------------------------------------------------
  # Single message actions
  #----------------------------------------------------------------------------

  $scope.onToggleMessageFlag = (message) ->
    prevState = message.flagged
    message.flagged = !prevState
    MessageService.flagMessages([message], message.flagged, () ->
      $scope.updateItems()
    )

  $scope.onForwardMessage = (message) ->
    initialText = '"' + message.text + '"'

    $uibModal.open({templateUrl: 'composeModal.html', controller: 'ComposeModalController', resolve: {
      title: () -> "Forward",
      initialText: () -> initialText,
      maxLength: () -> OUTGOING_TEXT_MAX_LEN,
    }})
    .result.then((data) ->
      MessageService.forwardMessage(message, data.text, data.urn, () ->
        UtilsService.displayAlert('success', "Message forwarded to " + data.urn.path)
      )
    )

  $scope.onCaseFromMessage = (message) ->
    if message.case
      CaseService.navigateToCase(message.case, null)
      return

    partners = if $scope.user.partner then null else $scope.partners
    resolve = {message: (() -> message), summaryMaxLength: (() -> CASE_SUMMARY_MAX_LEN), partners: (() -> partners)}
    $uibModal.open({templateUrl: 'newCaseModal.html', controller: 'NewCaseModalController', resolve: resolve})
    .result.then((result) ->
      CaseService.openCase(message, result.summary, result.assignee, (caseObj, isNew) ->
          withAlert = if !isNew then 'open_found_existing' else null
          CaseService.navigateToCase(caseObj, withAlert)
      )
    )

  $scope.onLabelMessage = (message) ->
    UtilsService.labelModal("Labels", "Update the labels for this message. This determines which other partner organizations can view this message.", $scope.labels, message.labels, (selectedLabels) ->
      MessageService.relabelMessage(message, selectedLabels, () ->
        $scope.updateItems()
      )
    )

  $scope.onShowMessageHistory = (message) ->
    $uibModal.open({templateUrl: 'messageHistory.html', controller: 'MessageHistoryModalController', resolve: {
      message: () -> message
    }})
]


#============================================================================
# Outgoing messages controller
#============================================================================
controllers.controller 'OutgoingController', [ '$scope', '$controller', 'OutgoingService', ($scope, $controller, OutgoingService) ->
  $controller('BaseItemsController', {$scope: $scope})

  $scope.init = () ->
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.activeSearch = $scope.buildSearch()

    $scope.$on('activeContactChange', () ->
      $scope.onResetSearch()
    )

  $scope.buildSearch = () ->
    search = angular.copy($scope.searchFields)
    search.folder = $scope.folder
    search.contact = $scope.activeContact
    search.timeCode = Date.now()
    return search

  $scope.searchFieldDefaults = () -> { text: null }

  $scope.fetchOldItems = (callback) ->
    OutgoingService.fetchOld($scope.activeSearch, $scope.startTime, $scope.oldItemsPage, callback)
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

    $scope.$on('activeLabelChange', () ->
      $scope.onResetSearch()
    )

  $scope.getItemFilter = () ->
    if $scope.folder == 'open'
      return (item) -> !item.is_closed
    else if $scope.folder == 'closed'
      return (item) -> item.is_closed

  $scope.buildSearch = () ->
    search = angular.copy($scope.searchFields)
    search.folder = $scope.folder
    search.label = $scope.activeLabel
    search.timeCode = Date.now()
    return search

  $scope.searchFieldDefaults = () -> { assignee: $scope.user.partner }

  $scope.onExportSearch = () ->
    UtilsService.confirmModal("Export the current case search?", null, () ->
      CaseService.startExport($scope.activeSearch, () ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")
      )
    )

  $scope.fetchOldItems = (callback) ->
    CaseService.fetchOld($scope.activeSearch, $scope.startTime, $scope.oldItemsPage, callback)

  $scope.refreshNewItems = () ->
    timeCode = $scope.activeSearch.timeCode
    afterTime = $scope.newItemsMaxTime or $scope.startTime
    $scope.newItemsMaxTime = new Date()

    CaseService.fetchNew($scope.activeSearch, afterTime, $scope.newItemsMaxTime, (items) ->
      if timeCode == $scope.activeSearch.timeCode
        $scope.items = items.concat($scope.items)

      $timeout($scope.refreshNewItems, INTERVAL_CASES_NEW)
    )

  $scope.onClickCase = (caseObj) ->
    UtilsService.navigate('/case/read/' + caseObj.id + '/')
])


#============================================================================
# Case view controller
#============================================================================
controllers.controller 'CaseController', [ '$scope', '$window', '$timeout', 'CaseService', 'MessageService', 'UtilsService', ($scope, $window, $timeout, CaseService, MessageService, UtilsService) ->

  $scope.caseObj = $window.contextData.case_obj
  $scope.allPartners = $window.contextData.all_partners
  $scope.allLabels = $window.contextData.all_labels

  $scope.newMessage = ''
  $scope.sending = false

  $scope.init = (maxMsgChars) ->
    $scope.msgCharsRemaining = $scope.maxMsgChars = maxMsgChars

    $scope.refresh()

  $scope.refresh = () ->
    CaseService.fetchCase($scope.caseObj.id, (caseObj) ->
      caseObj.contact = $scope.caseObj.contact  # refresh doesn't include contact
      $scope.caseObj = caseObj

      $timeout($scope.refresh, INTERVAL_CASE_INFO)
    )

  $scope.onEditLabels = ->
    UtilsService.labelModal("Labels", "Update the labels for this case. This determines which other partner organizations can view this case.", $scope.allLabels, $scope.caseObj.labels, (selectedLabels) ->
      CaseService.relabelCase($scope.caseObj, selectedLabels, () ->
        $scope.$broadcast('timelineChanged')
      )
    )

  $scope.onEditSummary = ->
    UtilsService.editModal("Edit Summary", $scope.caseObj.summary, CASE_SUMMARY_MAX_LEN, (text) ->
      CaseService.updateCaseSummary($scope.caseObj, text, () ->
        $scope.$broadcast('timelineChanged')
      )
    )

  #----------------------------------------------------------------------------
  # Messaging
  #----------------------------------------------------------------------------

  $scope.sendMessage = ->
    $scope.sending = true

    try
      CaseService.replyToCase($scope.caseObj, $scope.newMessage, () ->
        $scope.newMessage = ''
        $scope.sending = false
        $scope.$broadcast('timelineChanged')
      )
    catch e
      $window.Raven.captureException(e)

  $scope.onNewMessageChanged = ->
    $scope.msgCharsRemaining = $scope.maxMsgChars - $scope.newMessage.length

  #----------------------------------------------------------------------------
  # Case actions
  #----------------------------------------------------------------------------

  $scope.onAddNote = () ->
    UtilsService.noteModal("Add Note", null, null, CASE_NOTE_MAX_LEN, (note) ->
      CaseService.noteCase($scope.caseObj, note, () ->
        $scope.$broadcast('timelineChanged')
      )
    )

  $scope.onReassign = () ->
    UtilsService.assignModal("Re-assign", null, $scope.allPartners, (assignee) ->
      CaseService.reassignCase($scope.caseObj, assignee, () ->
        $scope.$broadcast('timelineChanged')
      )
    )

  $scope.onClose = () ->
    UtilsService.noteModal("Close", "Close this case?", 'danger', CASE_NOTE_MAX_LEN, (note) ->
      CaseService.closeCase($scope.caseObj, note, () ->
        UtilsService.navigate('/')
      )
    )

  $scope.onReopen = () ->
    UtilsService.noteModal("Re-open", "Re-open this case?", null, CASE_NOTE_MAX_LEN, (note) ->
      CaseService.reopenCase($scope.caseObj, note, () ->
        $scope.$broadcast('timelineChanged')
      )
    )
]


#============================================================================
# Case timeline controller
#============================================================================
controllers.controller 'CaseTimelineController', [ '$scope', '$timeout', 'CaseService', ($scope, $timeout, CaseService) ->

  $scope.timeline = []
  $scope.itemsMaxTime = null

  $scope.init = () ->
    $scope.$on('timelineChanged', () ->
      $scope.refreshItems(false)
    )

    $scope.refreshItems(true)

  $scope.refreshItems = (repeat) ->

    CaseService.fetchTimeline($scope.caseObj, $scope.itemsMaxTime, (events, maxTime) ->
      $scope.timeline = $scope.timeline.concat(events)
      $scope.itemsMaxTime = maxTime

      if repeat
        $timeout((() -> $scope.refreshItems(true)), INTERVAL_CASE_TIMELINE)
    )
]


#============================================================================
# Partner view controller
#============================================================================
controllers.controller 'PartnerController', [ '$scope', '$window', 'UtilsService', 'PartnerService', ($scope, $window, UtilsService, PartnerService) ->

  $scope.partner = $window.contextData.partner
  $scope.usersFetched = false
  $scope.users = []

  $scope.onTabSelect = (tab) ->
    if tab == 'users' and not $scope.usersFetched
      PartnerService.fetchUsers($scope.partner).then((users) ->
        $scope.usersFetched = true
        $scope.users = users
      )

  $scope.onDeletePartner = () ->
    UtilsService.confirmModal("Remove this partner organization?", 'danger', () ->
      PartnerService.deletePartner($scope.partner).then(() ->
        UtilsService.navigate('/partner/')
      )
    )
]


#============================================================================
# Partner replies controller
#============================================================================
controllers.controller 'PartnerRepliesController', [ '$scope', '$window', '$controller', 'UtilsService', 'OutgoingService', ($scope, $window, $controller, UtilsService, OutgoingService) ->
  $controller('BaseItemsController', {$scope: $scope})

  $scope.init = () ->
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.activeSearch = $scope.buildSearch()

    # trigger search if date range is changed
    $scope.$watchGroup(['searchFields.after', 'searchFields.before'], () ->
      $scope.onSearch()
    )

  $scope.buildSearch = () ->
    search = angular.copy($scope.searchFields)
    search.partner = $scope.partner

    # searching up to a date means including anything on the date
    if search.before
      search.before.setHours(23, 59, 59, 999)

    return search

  $scope.searchFieldDefaults = () -> { after: null, before: null }

  $scope.fetchOldItems = (callback) ->
    OutgoingService.fetchReplies($scope.activeSearch, $scope.startTime, $scope.oldItemsPage, callback)

  $scope.onExportSearch = () ->
    UtilsService.confirmModal("Export the current search?", null, () ->
      OutgoingService.startReplyExport($scope.activeSearch, () ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")
      )
    )
]


#============================================================================
# User view controller
#============================================================================
controllers.controller 'UserController', [ '$scope', '$window', 'UtilsService', 'UserService', ($scope, $window, UtilsService, UserService) ->

  $scope.user = $window.contextData.user

  $scope.onDeleteUser = () ->
    UtilsService.confirmModal("Delete this user?", 'danger', () ->
      UserService.deleteUser($scope.user).then(() ->
        UtilsService.navigateBack()
      );
    )
]


#============================================================================
# Date range controller
#============================================================================
controllers.controller 'DateRangeController', [ '$scope', ($scope) ->
  $scope.afterOpen = false
  $scope.afterOptions = { minDate: null, maxDate: new Date() }
  $scope.beforeOpen = false
  $scope.beforeOptions = { minDate: null, maxDate: new Date() }

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
    $scope.beforeOptions.minDate = $scope.searchFields.after

  $scope.onBeforeChange = () ->
    # don't allow after to be more than before
    $scope.afterOptions.maxDate = $scope.searchFields.before
]