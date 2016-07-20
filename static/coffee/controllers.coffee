#============================================================================
# Component controllers
#============================================================================

controllers = angular.module('cases.controllers', ['cases.services', 'cases.modals']);


# Component refresh intervals
INTERVAL_CASE_INFO = 30000
INTERVAL_CASE_TIMELINE = 30000

INFINITE_SCROLL_MAX_ITEMS = 1000

# Form constraints
CASE_SUMMARY_MAX_LEN = 255
CASE_NOTE_MAX_LEN = 1024
OUTGOING_TEXT_MAX_LEN = 480


#============================================================================
# Inbox controller (DOM parent of messages and cases)
#============================================================================
controllers.controller('InboxController', ['$scope', '$window', '$location', 'LabelService', 'UtilsService', ($scope, $window, $location, LabelService, UtilsService) ->

  $scope.user = $window.contextData.user
  $scope.labels = $window.contextData.labels
  $scope.groups = $window.contextData.groups

  $scope.activeLabel = null
  $scope.activeContact = null
  $scope.inactiveLabels = $scope.labels

  $scope.init = (folder, serverTime) ->
    $scope.folder = folder
    $scope.startTime = new Date(serverTime)

    $scope.$on('$locationChangeSuccess', () ->
      params = $location.search()
      if 'label' of params
        $window.console.log(params.label)
        initialLabel = utils.find($scope.labels, 'name', params.label)
      else
        initialLabel = null

      if $scope.activeLabel != initialLabel
        $scope.activateLabel(initialLabel)
    )

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

  $scope.filterDisplayLabels = (labels) ->
    # filters out the active label from the given set of message labels
    if $scope.activeLabel then (l for l in labels when l.id != $scope.activeLabel.id) else labels
])


#============================================================================
# Base controller class for controllers which have tabs
#============================================================================
controllers.controller('BaseTabsController', ['$scope', '$location', ($scope, $location) ->
  $scope.initialisedTabs = []

  path = $location.path()
  if path
    initialTabSlug = path.substring(1)  # ignore initial /
    $scope.active = $scope.tabSlugs.indexOf(initialTabSlug)
  else
    $scope.active = 0

  $scope.onTabSelect = (tab) ->
    slug = $scope.tabSlugs[tab]

    $location.path('/' + slug)

    if tab not in $scope.initialisedTabs
      $scope.onTabInit(slug)
      $scope.initialisedTabs.push(tab)
])


#============================================================================
# Base controller class for controllers which display fetched items with
# infinite scrolling, e.g. lists of messages, cases etc
#============================================================================
controllers.controller('BaseItemsController', ['$scope', 'UtilsService', ($scope, UtilsService) ->

  $scope.items = []
  $scope.oldItemsLoading = false
  $scope.oldItemsPage = 0
  $scope.oldItemsMore = true
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

    $scope.fetchOldItems($scope.activeSearch, $scope.startTime, $scope.oldItemsPage).then((data) ->
      $scope.items = $scope.items.concat(data.results)
      $scope.oldItemsMore = data.hasMore
      $scope.oldItemsLoading = false

      if forSelectAll
        for item in items
          item.selected = true
        $scope.updateItems(false)
        if $scope.oldItemsMore and $scope.items.length < INFINITE_SCROLL_MAX_ITEMS
          $scope.loadOldItems(true)
    ).catch((error) ->
      UtilsService.displayAlert('error', "Problem communicating with the server")

      Raven.captureMessage(error.statusText + " (" + error.status + ")", {
        user: if $scope.user then {id: $scope.user.id} else null,
        extra: {xhr_url: error.config.url}
      })
    )

  $scope.isInfiniteScrollEnabled = () ->
    not $scope.oldItemsLoading and $scope.oldItemsMore and $scope.items.length < INFINITE_SCROLL_MAX_ITEMS

  $scope.hasTooManyItemsToDisplay = () ->
    $scope.oldItemsMore and $scope.items.length >= INFINITE_SCROLL_MAX_ITEMS
])


#============================================================================
# Incoming messages controller
#============================================================================
controllers.controller('MessagesController', ['$scope', '$timeout', '$uibModal', '$controller', 'CaseService', 'MessageService', 'PartnerService', 'UtilsService', ($scope, $timeout, $uibModal, $controller, CaseService, MessageService, PartnerService, UtilsService) ->
  $controller('BaseItemsController', {$scope: $scope})

  $scope.advancedSearch = false
  $scope.expandedMessageId = null

  $scope.init = () ->
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.activeSearch = $scope.buildSearch()

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

    # searching up to a date means including anything on the date
    if search.before
      search.before.setHours(23, 59, 59, 999)

    return search

  $scope.searchFieldDefaults = () -> { text: null, groups: [], after: null, before: null, archived: false }

  $scope.setAdvancedSearch = (state) ->
    $scope.advancedSearch = state

  $scope.onExportSearch = () ->
    UtilsService.confirmModal("Export the current message search?").then(() ->
      MessageService.startExport($scope.activeSearch).then(() ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")
      )
    )

  $scope.fetchOldItems = (search, startTime, page) ->
    return MessageService.fetchOld(search, startTime, page)

  $scope.onExpandMessage = (message) ->
    $scope.expandedMessageId = message.id

  #----------------------------------------------------------------------------
  # Selection actions
  #----------------------------------------------------------------------------

  $scope.onLabelSelection = (label) ->
    UtilsService.confirmModal('Apply the label <strong>' + label.name + '</strong> to the selected messages?').then(() ->
      MessageService.bulkLabel($scope.selection, label).then(() ->
        $scope.updateItems()
      )
    )

  $scope.onFlagSelection = () ->
    UtilsService.confirmModal('Flag the selected messages?').then(() ->
      MessageService.bulkFlag($scope.selection, true).then(() ->
        $scope.updateItems()
      )
    )

  $scope.onReplyToSelection = () ->
    $uibModal.open({templateUrl: '/partials/modal_reply.html', controller: 'ReplyModalController', resolve: {maxLength: (() -> OUTGOING_TEXT_MAX_LEN)}})
    .result.then((text) ->
      MessageService.bulkReply($scope.selection, text).then(() ->
        MessageService.bulkArchive($scope.selection).then(() ->
          UtilsService.displayAlert('success', "Reply sent and messages archived")
          $scope.updateItems()
        )
      )
    )

  $scope.onArchiveSelection = () ->
    UtilsService.confirmModal('Archive the selected messages? This will remove them from your inbox.').then(() ->
      MessageService.bulkArchive($scope.selection).then(() ->
        $scope.updateItems()
      )
    )

  $scope.onRestoreSelection = () ->
    UtilsService.confirmModal('Restore the selected messages? This will put them back in your inbox.').then(() ->
      MessageService.bulkRestore($scope.selection).then(() ->
        $scope.updateItems()
      )
    )

  #----------------------------------------------------------------------------
  # Single message actions
  #----------------------------------------------------------------------------

  $scope.onToggleMessageFlag = (message) ->
    MessageService.bulkFlag([message], !message.flagged).then(() ->
      $scope.updateItems()
    )

  $scope.onForwardMessage = (message) ->
    initialText = '"' + message.text + '"'

    UtilsService.composeModal("Forward", initialText, OUTGOING_TEXT_MAX_LEN).then((data) ->
      MessageService.forward(message, data.text, data.urn).then(() ->
        UtilsService.displayAlert('success', "Message forwarded to " + data.urn.path)
      )
    )

  $scope.onCaseFromMessage = (message) ->
    if message.case
      UtilsService.navigate('/case/read/' + message.case.id + '/')
      return

    if $scope.user.partner
      # if user belongs to a partner, case will be assigned to them
      newCaseFromMessage(message, null)
    else
      # if not then they can choose an assignee
      PartnerService.fetchAll().then((partners) ->
        newCaseFromMessage(message, partners)
      )

  $scope.onLabelMessage = (message) ->
    UtilsService.labelModal("Labels", "Update the labels for this message. This determines which other partner organizations can view this message.", $scope.labels, message.labels).then((selectedLabels) ->
      MessageService.relabel(message, selectedLabels).then(() ->
        $scope.updateItems()
      )
    )

  $scope.onShowMessageHistory = (message) ->
    $uibModal.open({templateUrl: '/partials/modal_messagehistory.html', controller: 'MessageHistoryModalController', resolve: {
      message: () -> message
    }})

  newCaseFromMessage = (message, possibleAssignees) ->
    UtilsService.newCaseModal(message.text, CASE_SUMMARY_MAX_LEN, possibleAssignees).then((data) ->
      CaseService.open(message, data.summary, data.assignee).then((caseObj) ->
          caseUrl = '/case/read/' + caseObj.id + '/'
          if !caseObj.is_new
            caseUrl += '?alert=open_found_existing'
          UtilsService.navigate(caseUrl)
      )
    )
])


#============================================================================
# Outgoing messages controller
#============================================================================
controllers.controller('OutgoingController', ['$scope', '$controller', 'OutgoingService', ($scope, $controller, OutgoingService) ->
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
    return search

  $scope.searchFieldDefaults = () -> { text: null }

  $scope.fetchOldItems = (search, startTime, page) ->
    return OutgoingService.fetchOld(search, startTime, page)
])


#============================================================================
# Cases listing controller
#============================================================================
controllers.controller('CasesController', ['$scope', '$timeout', '$controller', 'CaseService', 'UtilsService', ($scope, $timeout, $controller, CaseService, UtilsService) ->
  $controller('BaseItemsController', {$scope: $scope})

  $scope.init = () ->
    $scope.searchFields = $scope.searchFieldDefaults()
    $scope.activeSearch = $scope.buildSearch()

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
    return search

  $scope.searchFieldDefaults = () -> { assignee: $scope.user.partner }

  $scope.onExportSearch = () ->
    UtilsService.confirmModal("Export the current case search?").then(() ->
      CaseService.startExport($scope.activeSearch).then(() ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")
      )
    )

  $scope.fetchOldItems = (search, startTime, page) ->
    return CaseService.fetchOld(search, startTime, page)

  $scope.onClickCase = (caseObj) ->
    UtilsService.navigate('/case/read/' + caseObj.id + '/')
])


#============================================================================
# Org home controller
#============================================================================
controllers.controller('HomeController', ['$scope', '$controller', 'LabelService', 'PartnerService', 'StatisticsService', 'UserService', 'UtilsService', ($scope, $controller, LabelService, PartnerService, StatisticsService, UserService, UtilsService) ->
  $scope.tabSlugs = ['summary', 'partners', 'labels', 'users']

  $controller('BaseTabsController', {$scope: $scope})

  $scope.partners = []
  $scope.users = []

  $scope.onTabInit = (tab) ->
    if tab == 'summary'
      StatisticsService.repliesChart().then((chart) ->
        Highcharts.chart('chart-replies-by-month', {
          chart: {type: 'column'},
          title: {text: null},
          xAxis: {categories: chart.categories},
          yAxis: {min: 0, title: {text: 'Replies Sent'}},
          legend: {enabled: false},
          series: [{name: 'Replies', data: chart.series}],
        })
      )
      StatisticsService.labelsPieChart().then((chart) ->
        Highcharts.chart('chart-most-common-labels', {
          chart: {type: 'pie'},
          title: {text: "Message labels in last 30 days"},
          series: [{name: 'Messages', data: chart.series}],
        })
      )
      StatisticsService.incomingChart().then((chart) ->
        Highcharts.chart('chart-incoming-by-day', {
          title: {text: null},
          xAxis: {type: 'datetime'},
          yAxis: {min: 0, title: {text: "Messages Received"}},
          legend: {enabled: false},
          series: [{name: "Messages", data: chart.series}],
        })
      )
    else if tab == 'partners'
      PartnerService.fetchAll(true).then((partners) ->
        $scope.partners = partners
      )
    else if tab == 'labels'
      LabelService.fetchAll(true).then((labels) ->
        $scope.labels = labels
      )
    else if tab == 'users'
      UserService.fetchNonPartner(true).then((users) ->
        $scope.users = users
      )

  $scope.onExportPartnerStats = () ->
    UtilsService.dateRangeModal("Export", "Export partner statistics between the following dates").then((data) ->
      StatisticsService.dailyCountExport('P', data.after, data.before).then(() ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")
      )
    )

  $scope.onExportLabelStats = () ->
    UtilsService.dateRangeModal("Export", "Export label statistics between the following dates").then((data) ->
      StatisticsService.dailyCountExport('L', data.after, data.before).then(() ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")
      )
    )
])


#============================================================================
# Case view controller
#============================================================================
controllers.controller('CaseController', ['$scope', '$window', '$timeout', 'CaseService', 'ContactService', 'MessageService', 'PartnerService', 'UtilsService', ($scope, $window, $timeout, CaseService, ContactService, MessageService, PartnerService, UtilsService) ->

  $scope.allLabels = $window.contextData.all_labels
  
  $scope.caseObj = null
  $scope.contact = null
  $scope.newMessage = ''
  $scope.sending = false

  $scope.init = (caseId, maxMsgChars) ->
    $scope.caseId = caseId
    $scope.msgCharsRemaining = $scope.maxMsgChars = maxMsgChars

    $scope.refresh()

  $scope.refresh = () ->
    CaseService.fetchSingle($scope.caseId).then((caseObj) ->
      $scope.caseObj = caseObj

      if not $scope.contact
        ContactService.fetch(caseObj.contact.id).then((contact) ->
          $scope.contact = contact
        )

      $timeout($scope.refresh, INTERVAL_CASE_INFO)
    )

  $scope.onEditLabels = ->
    UtilsService.labelModal("Labels", "Update the labels for this case. This determines which other partner organizations can view this case.", $scope.allLabels, $scope.caseObj.labels).then((selectedLabels) ->
      CaseService.relabel($scope.caseObj, selectedLabels).then(() ->
        $scope.$broadcast('timelineChanged')
      )
    )

  $scope.onEditSummary = ->
    UtilsService.editModal("Edit Summary", $scope.caseObj.summary, CASE_SUMMARY_MAX_LEN).then((text) ->
      CaseService.updateSummary($scope.caseObj, text).then(() ->
        $scope.$broadcast('timelineChanged')
      )
    )

  #----------------------------------------------------------------------------
  # Messaging
  #----------------------------------------------------------------------------

  $scope.sendMessage = ->
    $scope.sending = true

    try
      CaseService.replyTo($scope.caseObj, $scope.newMessage).then(() ->
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

  $scope.onWatch = () ->
    UtilsService.confirmModal("Receive notifications for activity in this case?").then(() ->
      CaseService.watch($scope.caseObj)
    )

  $scope.onUnwatch = () ->
    UtilsService.confirmModal("Stop receiving notifications for activity in this case?").then(() ->
      CaseService.unwatch($scope.caseObj)
    )

  $scope.onAddNote = () ->
    UtilsService.noteModal("Add Note", null, null, CASE_NOTE_MAX_LEN).then((note) ->
      CaseService.addNote($scope.caseObj, note).then(() ->
        $scope.$broadcast('timelineChanged')
      )
    )

  $scope.onReassign = () ->
    PartnerService.fetchAll().then((partners) ->
      UtilsService.assignModal("Re-assign", null, partners).then((assignee) ->
        CaseService.reassign($scope.caseObj, assignee).then(() ->
          $scope.$broadcast('timelineChanged')
        )
      )
    )

  $scope.onClose = () ->
    UtilsService.noteModal("Close", "Close this case?", 'danger', CASE_NOTE_MAX_LEN).then((note) ->
      CaseService.close($scope.caseObj, note).then(() ->
        UtilsService.navigate('/')
      )
    )

  $scope.onReopen = () ->
    UtilsService.noteModal("Re-open", "Re-open this case?", null, CASE_NOTE_MAX_LEN).then((note) ->
      CaseService.reopen($scope.caseObj, note).then(() ->
        $scope.$broadcast('timelineChanged')
      )
    )
])


#============================================================================
# Case timeline controller
#============================================================================
controllers.controller('CaseTimelineController', ['$scope', '$timeout', 'CaseService', ($scope, $timeout, CaseService) ->

  $scope.timeline = []
  $scope.itemsMaxTime = null

  $scope.init = () ->
    $scope.$on('timelineChanged', () ->
      $scope.refreshItems(false)
    )

    $scope.refreshItems(true)

  $scope.refreshItems = (repeat) ->

    CaseService.fetchTimeline({id: $scope.caseId}, $scope.itemsMaxTime).then((data) ->
      $scope.timeline = $scope.timeline.concat(data.results)
      $scope.itemsMaxTime = data.maxTime

      if repeat
        $timeout((() -> $scope.refreshItems(true)), INTERVAL_CASE_TIMELINE)
    )
])


#============================================================================
# Label dashboard controller
#============================================================================
controllers.controller('LabelController', ['$scope', '$window', '$controller', 'UtilsService', 'LabelService', 'StatisticsService', ($scope, $window, $controller, UtilsService, LabelService, StatisticsService) ->
  $scope.tabSlugs = ['summary']
  
  $controller('BaseTabsController', {$scope: $scope})

  $scope.label = $window.contextData.label

  $scope.onTabInit = (tab) ->
    if tab == 'summary'
      StatisticsService.incomingChart($scope.label).then((chart) ->
        Highcharts.chart('chart-incoming-by-day', {
          title: {text: null},
          xAxis: {type: 'datetime'},
          yAxis: {min: 0, title: {text: "Messages"}},
          legend: {enabled: false},
          series: [{name: "Messages", data: chart.series}],
        })
      )

  $scope.onWatch = () ->
    UtilsService.confirmModal("Receive notifications for new messages with this label?").then(() ->
      LabelService.watch($scope.label)
    )

  $scope.onUnwatch = () ->
    UtilsService.confirmModal("Stop receiving notifications for new messages with this label?").then(() ->
      LabelService.unwatch($scope.label)
    )

  $scope.onDeleteLabel = () ->
    UtilsService.confirmModal("Delete this label?", 'danger').then(() ->
      LabelService.delete($scope.label).then(() ->
        UtilsService.navigate('/label/')
      )
    )
])


#============================================================================
# Partner dashboard controller
#============================================================================
controllers.controller('PartnerController', ['$scope', '$window', '$controller', 'UtilsService', 'PartnerService', 'StatisticsService', 'UserService', ($scope, $window, $controller, UtilsService, PartnerService, StatisticsService, UserService) ->
  $scope.tabSlugs = ['summary', 'replies', 'users']

  $controller('BaseTabsController', {$scope: $scope})

  $scope.partner = $window.contextData.partner
  $scope.users = []

  $scope.onTabInit = (tab) ->
    if tab == 'summary'
      StatisticsService.repliesChart($scope.partner, null).then((chart) ->
        Highcharts.chart('chart-replies-by-month', {
          chart: {type: 'column'},
          title: {text: null},
          xAxis: {categories: chart.categories},
          yAxis: {min: 0, title: {text: "Replies"}},
          legend: {enabled: false},
          series: [{name: "Replies", data: chart.series}],
        })
      )
    else if tab == 'users'
      UserService.fetchInPartner($scope.partner, true).then((users) ->
        $scope.users = users
      )

  $scope.onDeletePartner = () ->
    UtilsService.confirmModal("Remove this partner organization?", 'danger').then(() ->
      PartnerService.delete($scope.partner).then(() ->
        UtilsService.navigate('/partner/')
      )
    )
])


#============================================================================
# Partner replies controller
#============================================================================
controllers.controller('PartnerRepliesController', ['$scope', '$window', '$controller', 'UtilsService', 'OutgoingService', ($scope, $window, $controller, UtilsService, OutgoingService) ->
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

  $scope.fetchOldItems = (search, startTime, page) ->
    return OutgoingService.fetchReplies(search, startTime, page)

  $scope.onExportSearch = () ->
    UtilsService.confirmModal("Export the current search?").then(() ->
      OutgoingService.startReplyExport($scope.activeSearch).then(() ->
        UtilsService.displayAlert('success', "Export initiated and will be sent to your email address when complete")
      )
    )
])


#============================================================================
# User view controller
#============================================================================
controllers.controller('UserController', ['$scope', '$controller', '$window', 'StatisticsService', 'UserService', 'UtilsService', ($scope, $controller, $window, StatisticsService, UserService, UtilsService) ->
  $scope.tabSlugs = ['summary']

  $controller('BaseTabsController', {$scope: $scope})

  $scope.user = $window.contextData.user

  $scope.onTabInit = (tab) ->
    if tab == 'summary'
      StatisticsService.repliesChart(null, $scope.user).then((chart) ->
        Highcharts.chart('chart-replies-by-month', {
          chart: {type: 'column'},
          title: {text: null},
          xAxis: {categories: chart.categories},
          yAxis: {min: 0, title: {text: "Replies"}},
          legend: {enabled: false},
          series: [{name: "Replies", data: chart.series}]
        })
      )

  $scope.onDeleteUser = () ->
    UtilsService.confirmModal("Delete this user?", 'danger').then(() ->
      UserService.delete($scope.user).then(() ->
        UtilsService.navigateBack()
      )
    )
])


#============================================================================
# Date range controller
#============================================================================
controllers.controller('DateRangeController', ['$scope', ($scope) ->
  $scope.afterOpen = false
  $scope.afterOptions = { minDate: null, maxDate: new Date() }
  $scope.beforeOpen = false
  $scope.beforeOptions = { minDate: null, maxDate: new Date() }

  $scope.format = 'MMM dd, yyyy'

  $scope.init = (afterModel, beforeModel) ->
    $scope.$watch(afterModel, () ->
      # don't allow before to be less than after
      $scope.beforeOptions.minDate = $scope.$eval(afterModel)
    )
    $scope.$watch(beforeModel, () ->
      # don't allow before to be less than after
      $scope.afterOptions.maxDate = $scope.$eval(beforeModel)
    )

  $scope.openAfter = ($event) ->
    $event.preventDefault()
    $event.stopPropagation()
    $scope.afterOpen = true

  $scope.openBefore = ($event) ->
    $event.preventDefault()
    $event.stopPropagation()
    $scope.beforeOpen = true
])
