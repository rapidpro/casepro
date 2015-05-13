#============================================================================
# Modal dialog controllers
#============================================================================

modals = angular.module('cases.modals', []);

URN_SCHEMES = {tel: "Phone", twitter: "Twitter"}


#=====================================================================
# Simple confirmation modal
#=====================================================================
modals.controller 'ConfirmModalController', [ '$scope', '$modalInstance', 'prompt', 'style', ($scope, $modalInstance, prompt, style) ->
  $scope.title = "Confirm"
  $scope.prompt = prompt
  $scope.style = style or 'primary'

  $scope.ok = () -> $modalInstance.close(true)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#=====================================================================
# Confirm with note modal
#=====================================================================
modals.controller 'NoteModalController', [ '$scope', '$modalInstance', 'title', 'prompt', 'style', ($scope, $modalInstance, title, prompt, style) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.style = style or 'primary'
  $scope.note = ''

  $scope.ok = () -> $modalInstance.close($scope.note)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#=====================================================================
# Edit text modal
#=====================================================================
modals.controller 'EditModalController', [ '$scope', '$modalInstance', 'title', 'initial', ($scope, $modalInstance, title, initial) ->
  $scope.title = title
  $scope.text = initial

  $scope.ok = () -> $modalInstance.close($scope.text)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#=====================================================================
# Reply to contact modal
#=====================================================================
modals.controller('ReplyModalController', [ '$scope', '$modalInstance', ($scope, $modalInstance) ->
  $scope.text = ''

  $scope.ok = () -> $modalInstance.close($scope.text)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
])


#=====================================================================
# Open new case modal
#=====================================================================
modals.controller 'NewCaseModalController', [ '$scope', '$modalInstance', 'message', 'partners', ($scope, $modalInstance, message, partners) ->
  $scope.summary = message.text
  $scope.partners = partners
  $scope.assignee = if partners then partners[0] else null

  $scope.ok = () -> $modalInstance.close($scope.summary, $scope.assignee)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#=====================================================================
# Assign to partner modal
#=====================================================================
modals.controller 'AssignModalController', [ '$scope', '$modalInstance', 'title', 'prompt', 'partners', ($scope, $modalInstance, title, prompt, partners) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.partners = partners
  $scope.assignee = partners[0]

  $scope.ok = () -> $modalInstance.close($scope.assignee)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#=====================================================================
# Edit item labels modal
#=====================================================================
modals.controller('LabelModalController', ['$scope', '$modalInstance', 'title', 'prompt', 'labels', 'initial', ($scope, $modalInstance, title, prompt, labels, initial) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.selection = ({label: l, selected: (l.id in (i.id for i in initial))} for l in labels)

  $scope.ok = () ->
    selectedLabels = (item.label for item in $scope.selection when item.selected)
    $modalInstance.close(selectedLabels)

  $scope.cancel = () -> $modalInstance.dismiss('cancel')
])


#=====================================================================
# Compose message to URN modal
#=====================================================================
modals.controller('ComposeModalController', ['$scope', '$modalInstance', 'title', 'initialText', ($scope, $modalInstance, title, initialText) ->
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


#=====================================================================
# Message history modal
#=====================================================================
modals.controller('MessageHistoryModalController', ['$scope', '$modalInstance', 'MessageService', 'message', ($scope, $modalInstance, MessageService, message) ->
  $scope.message = message
  $scope.loading = true

  MessageService.fetchHistory($scope.message, (actions)->
    $scope.actions = actions
    $scope.loading = false
  )

  $scope.close = () -> $modalInstance.dismiss('close')
])