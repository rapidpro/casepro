#============================================================================
# Modal dialog controllers
#============================================================================

modals = angular.module('cases.modals', []);

URN_SCHEMES = {tel: "Phone", twitter: "Twitter"}


#=====================================================================
# Simple confirmation modal
#=====================================================================
modals.controller 'ConfirmModalController', ['$scope', '$modalInstance', 'prompt', 'style', ($scope, $modalInstance, prompt, style) ->
  $scope.title = "Confirm"
  $scope.prompt = prompt
  $scope.style = style or 'primary'

  $scope.ok = () -> $modalInstance.close(true)
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#=====================================================================
# Confirm with note modal
#=====================================================================
modals.controller 'NoteModalController', ['$scope', '$modalInstance', 'title', 'prompt', 'style', 'maxLength', ($scope, $modalInstance, title, prompt, style, maxLength) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.style = style or 'primary'
  $scope.fields = {note: {val: '', maxLength: maxLength}}

  $scope.ok = () ->
    if $scope.form.$valid
      $modalInstance.close($scope.fields.note.val)

  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#=====================================================================
# Edit text modal
#=====================================================================
modals.controller 'EditModalController', ['$scope', '$modalInstance', 'title', 'initial', 'maxLength', ($scope, $modalInstance, title, initial, maxLength) ->
  $scope.title = title
  $scope.fields = {text: {val: initial, maxLength: maxLength}}

  $scope.ok = () ->
    if $scope.form.$valid
      $modalInstance.close($scope.fields.text.val)

  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#=====================================================================
# Reply to contacts modal
#=====================================================================
modals.controller('ReplyModalController', ['$scope', '$modalInstance', 'maxLength', ($scope, $modalInstance, maxLength) ->
  $scope.fields = {text: {val: '', maxLength: maxLength}}

  $scope.ok = () ->
    if $scope.form.$valid
      $modalInstance.close($scope.fields.text.val)

  $scope.cancel = () -> $modalInstance.dismiss('cancel')
])


#=====================================================================
# Open new case modal
#=====================================================================
modals.controller 'NewCaseModalController', ['$scope', '$modalInstance', 'message', 'summaryMaxLength', 'partners', ($scope, $modalInstance, message, summaryMaxLength, partners) ->
  $scope.partners = partners
  $scope.fields = {
    summary: {val: message.text, maxLength: summaryMaxLength},
    assignee: {val: if partners then partners[0] else null}
  }

  $scope.ok = () ->
    if $scope.form.$valid
      $modalInstance.close({summary: $scope.fields.summary.val, assignee: $scope.fields.assignee.val})
  $scope.cancel = () -> $modalInstance.dismiss('cancel')
]


#=====================================================================
# Assign to partner modal
#=====================================================================
modals.controller 'AssignModalController', ['$scope', '$modalInstance', 'title', 'prompt', 'partners', ($scope, $modalInstance, title, prompt, partners) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.partners = partners
  $scope.fields = { assignee: partners[0] }

  $scope.ok = () -> $modalInstance.close($scope.fields.assignee)
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
  $scope.fields = {
    urn: { scheme: null, path: '' },
    text: initialText
  }

  $scope.setScheme = (scheme) ->
    $scope.fields.urn.scheme = scheme
    $scope.urn_scheme_label = URN_SCHEMES[scheme]

  $scope.ok = () ->
    urn = {scheme: $scope.fields.urn.scheme, path: $scope.fields.urn.path, urn: ($scope.fields.urn.scheme + ':' + $scope.fields.urn.path)}
    $modalInstance.close({text: $scope.fields.text, urn: urn})

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