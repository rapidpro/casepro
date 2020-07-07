#============================================================================
# Modal dialog controllers
#============================================================================

modals = angular.module('cases.modals', []);

URN_SCHEMES = {tel: "Phone", twitter: "Twitter", mailto: "Email"}
ANYONE = {id: null, name: "-- Anyone --"}


#=====================================================================
# Simple confirmation modal
#=====================================================================
modals.controller 'ConfirmModalController', ['$scope', '$uibModalInstance', 'prompt', 'style', ($scope, $uibModalInstance, prompt, style) ->
  $scope.title = "Confirm"
  $scope.prompt = prompt
  $scope.style = style or 'primary'

  $scope.ok = () -> $uibModalInstance.close(true)
  $scope.cancel = () -> $uibModalInstance.dismiss(false)
]


#=====================================================================
# Confirm with note modal
#=====================================================================
modals.controller 'NoteModalController', ['$scope', '$uibModalInstance', 'title', 'prompt', 'style', 'maxLength', ($scope, $uibModalInstance, title, prompt, style, maxLength) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.style = style or 'primary'
  $scope.fields = {note: {val: '', maxLength: maxLength}}

  $scope.ok = () ->
    $scope.form.submitted = true

    if $scope.form.$valid
      $uibModalInstance.close($scope.fields.note.val)

  $scope.cancel = () -> $uibModalInstance.dismiss(false)
]


#=====================================================================
# Edit text modal
#=====================================================================
modals.controller 'EditModalController', ['$scope', '$uibModalInstance', 'title', 'initial', 'maxLength', ($scope, $uibModalInstance, title, initial, maxLength) ->
  $scope.title = title
  $scope.fields = {text: {val: initial, maxLength: maxLength}}

  $scope.ok = () ->
    if $scope.form.$valid
      $uibModalInstance.close($scope.fields.text.val)

  $scope.cancel = () -> $uibModalInstance.dismiss(false)
]


#=====================================================================
# Reply to contacts modal
#=====================================================================
modals.controller('ReplyModalController', ['$scope', 'FaqService', '$uibModalInstance', '$controller', 'selection', ($scope , FaqService, $uibModalInstance, $controller, selection) ->

  $scope.fields = {text: {val: ''}}
  $scope.sendToMany = if selection then true else false

  $scope.init = (faqOnly) ->
    $scope.searchField = $scope.searchFieldDefaults()
    $scope.search = $scope.buildSearch()
    $scope.fetchFaqs()
    $scope.fetchLanguages()
    $scope.lang = "Select language"
    $scope.faqOnly = faqOnly

  $scope.buildSearch = () ->
    search = angular.copy($scope.searchField)
    search.label = $scope.activeLabel
    return search

  $scope.filterByLanguage = (language) ->
    $scope.lang = language.name
    $scope.search.language = language.code
    FaqService.fetchFaqs($scope.search).then((results) ->
        $scope.replies = results
      )

  $scope.fetchFaqs = (label) ->
    if label
      $scope.search.label = label
      FaqService.fetchFaqs($scope.search).then((results) ->
        $scope.replies = results
      )
    else
      FaqService.fetchFaqs($scope.search).then((results) ->
        $scope.replies = results
      )

  $scope.fetchLanguages = () ->
    FaqService.fetchLanguages($scope.search).then((results) ->
      $scope.languages = results
    )

  $scope.searchFieldDefaults = () -> { text: null, language: null}

  $scope.setResponse = (faq)->
   $scope.fields.text.val = faq

  $scope.ok = () ->
    $scope.form.submitted = true
    if $scope.form.$valid
      $uibModalInstance.close($scope.fields.text.val)

  $scope.cancel = () -> $uibModalInstance.dismiss(false)
])


#=====================================================================
# Open new case modal
#=====================================================================
modals.controller 'NewCaseModalController', ['$scope', '$uibModalInstance', 'summaryInitial', 'summaryMaxLength', 'contact', 'partners', 'UserService', ($scope, $uibModalInstance, summaryInitial, summaryMaxLength, contact, partners, UserService) ->
  $scope.contact = contact
  $scope.partners = partners
  $scope.users = [ANYONE]

  $scope.fields = {
    summary: {val: summaryInitial, maxLength: summaryMaxLength},
    assignee: {val: if partners then partners[0] else null},
    user: {val: ANYONE}
  }

  $scope.refreshUserList = () ->
    UserService.fetchInPartner($scope.fields.assignee.val, false).then((users) ->
      $scope.users = [ANYONE].concat(users)
      $scope.fields.user.val = ANYONE
    )

  $scope.ok = () ->
    $scope.form.submitted = true
    if $scope.form.$valid
      $uibModalInstance.close({
        summary: $scope.fields.summary.val,
        assignee: $scope.fields.assignee.val,
        user: if $scope.fields.user.val.id then $scope.fields.user.val else null
      })
  $scope.cancel = () -> $uibModalInstance.dismiss(false)

  $scope.refreshUserList()
]


#=====================================================================
# Assign to partner modal
#=====================================================================
modals.controller 'AssignModalController', ['$scope', '$uibModalInstance', 'title', 'prompt', 'partners', 'UserService', ($scope, $uibModalInstance, title, prompt, partners, UserService) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.partners = partners
  $scope.users = [ANYONE]

  $scope.fields = { assignee: partners[0], user: ANYONE }

  $scope.refreshUserList = () ->
    UserService.fetchInPartner($scope.fields.assignee, false).then((users) ->
      $scope.users = [ANYONE].concat(users)
      $scope.fields.user = ANYONE
    )

  $scope.ok = () -> $uibModalInstance.close({
    assignee: $scope.fields.assignee,
    user: if $scope.fields.user.id then $scope.fields.user else null
  })
  $scope.cancel = () -> $uibModalInstance.dismiss(false)

  $scope.refreshUserList()
]


#=====================================================================
# Edit item labels modal
#=====================================================================
modals.controller('LabelModalController', ['$scope', '$uibModalInstance', 'title', 'prompt', 'labels', 'initial', ($scope, $uibModalInstance, title, prompt, labels, initial) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.selection = ({label: l, selected: (l.id in (i.id for i in initial))} for l in labels)

  $scope.ok = () ->
    selectedLabels = (item.label for item in $scope.selection when item.selected)
    $uibModalInstance.close(selectedLabels)

  $scope.cancel = () -> $uibModalInstance.dismiss(false)
])


#=====================================================================
# Compose message to URN modal
#=====================================================================
modals.controller('ComposeModalController', ['$scope', '$uibModalInstance', 'title', 'initial', ($scope, $uibModalInstance, title, initial) ->
  $scope.title = title
  $scope.fields = {
    urn: {scheme: null, path: ''},
    text: {val: initial}
  }

  $scope.setScheme = (scheme) ->
    $scope.fields.urn.scheme = scheme
    $scope.urn_scheme_label = URN_SCHEMES[scheme]

  $scope.ok = () ->
    $scope.form.submitted = true

    if $scope.form.$valid
      urn = {scheme: $scope.fields.urn.scheme, path: $scope.fields.urn.path, urn: ($scope.fields.urn.scheme + ':' + $scope.fields.urn.path)}
      $uibModalInstance.close({text: $scope.fields.text.val, urn: urn})

  $scope.cancel = () -> $uibModalInstance.dismiss(false)

  $scope.setScheme('tel')
])


#=====================================================================
# Message history modal
#=====================================================================
modals.controller('MessageHistoryModalController', ['$scope', '$uibModalInstance', 'MessageService', 'message', ($scope, $uibModalInstance, MessageService, message) ->
  $scope.message = message
  $scope.loading = true

  MessageService.fetchHistory($scope.message).then((actions)->
    $scope.actions = actions
    $scope.loading = false
  )

  $scope.close = () -> $uibModalInstance.dismiss(false)
])


#=====================================================================
# Date range modal
#=====================================================================
modals.controller('DateRangeModalController', ['$scope', '$uibModalInstance', 'title', 'prompt', ($scope, $uibModalInstance, title, prompt) ->
  $scope.title = title
  $scope.prompt = prompt
  $scope.fields = {after: utils.addMonths(new Date(), -6), before: new Date()}

  $scope.ok = () ->
    if $scope.form.$valid
      $uibModalInstance.close({after: $scope.fields.after, before: $scope.fields.before})

  $scope.cancel = () -> $uibModalInstance.dismiss(false)
])

#=====================================================================
# FAQ modal
#=====================================================================
modals.controller('FaqModalController', ['$scope', 'FaqService', 'LabelService', '$uibModalInstance', 'title', 'translation', 'faq', 'isFaq', ($scope, FaqService, LabelService, $uibModalInstance, title, translation, faq, isFaq) ->
  $scope.title = title
  $scope.faq = faq
  $scope.isFaq = isFaq

  $scope.init = () ->
    $scope.modalType()
    $scope.fetchAllLanguages()
    $scope.fetchLabels()

  $scope.modalType = () ->
    if isFaq == false
      $scope.fields = {
        question: {val: if translation then translation.question else ''}
        answer: {val: if translation then translation.answer else ''}
        parent: {val: faq.id}
        language: {val: if translation then translation.language else ''}
        labels: {val: ''}
        id: {val: if translation then translation.id else ''}
        }
    else if isFaq == true
      $scope.fields = {
        question: {val: if faq then faq.question else ''}
        answer: {val: if faq then faq.answer else ''}
        parent: {val: if faq then faq.parent else ''}
        language: {val: if faq then faq.language else ''}
        labels: {val: if faq then (l.id for l in faq.labels) else $scope.labels}
        id: {val: if faq then faq.id else ''}
      }

  $scope.fetchAllLanguages = () ->
    FaqService.fetchAllLanguages().then((results) ->
      $scope.iso_list = results
    )
  $scope.fetchLabels = () ->
    LabelService.fetchAll(true).then((labels) ->
      $scope.labels = labels
    )

  $scope.formatInput = ($model) ->
    inputLabel = $scope.fields.language.val.name
    angular.forEach $scope.iso_list, (language) ->
      if $model == language.code
        inputLabel = language.name
    inputLabel

  $scope.clearInput = () ->
    $scope.fields.language.val = ''

  $scope.ok = () ->
    $scope.form.submitted = true

    if $scope.form.$valid
      data = {question: $scope.fields.question.val, answer: $scope.fields.answer.val, parent: $scope.fields.parent.val, language: $scope.fields.language.val.code, labels: $scope.fields.labels.val, id: $scope.fields.id.val}
      $uibModalInstance.close(data)

  $scope.cancel = () -> $uibModalInstance.dismiss(false)
])
