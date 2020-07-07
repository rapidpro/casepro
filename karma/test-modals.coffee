# Unit tests for our Angular modal controllers (controllers listed A-Z)

describe('modals:', () ->
  $controller = null
  $rootScope = null
  $q = null
  FaqService = null
  LabelService = null
  MessageService = null
  UserService = null

  $scope = null
  modalInstance = null
  test = null

  beforeEach(() ->
    module('cases')

    inject((_$controller_, _$rootScope_, _$q_, _MessageService_, _FaqService_, _LabelService_, _UserService_) ->
      $controller = _$controller_
      $rootScope = _$rootScope_
      $q = _$q_
      FaqService = _FaqService_
      LabelService = _LabelService_
      MessageService = _MessageService_
      UserService = _UserService_
    )

    $scope = $rootScope.$new()

    modalInstance = {
      close: jasmine.createSpy('modalInstance.close'),
      dismiss: jasmine.createSpy('modalInstance.dismiss'),
    }

    test = {
      # users
      user1: {id: 101, name: "Tom McTest", partner: null},

      # labels
      tea: {id: 201, name: "Tea"},
      coffee: {id: 202, name: "Coffee"},

      # partners
      moh: {id: 301, name: "MOH"},
      who: {id: 302, name: "WHO"},

      # language
      language1: {code: "eng", name: "English"},
      language2: {code: "afr", name: "Afrikaans"},

      # FAQs
      faq1: {id: 401, question: "Am I pregnant?", answer: "yes", language: {code: "eng", name: "English"}, labels: [{id: 201, name: "Tea"}, {id: 202, name: "Coffee"}], parent: null},

      # translation
      translation1: {id: 601, question: "Is ek swanger", answer: "ja", language: {code: "afr", name: "Afrikaans"}, labels: {id: 201, name: "Tea"}, parent: 401},

      msg1: {id: 501, text: "Hello"}
    }
  )

  it('AssignModalController', () ->
    $controller('AssignModalController', {$scope: $scope, $uibModalInstance: modalInstance, title: "Title", prompt: "OK?", partners: [test.moh, test.who]})

    expect($scope.fields.assignee).toEqual(test.moh)
    expect($scope.fields.user).toEqual({id: null, name: "-- Anyone --"})
    expect($scope.users).toEqual([{id: null, name: "-- Anyone --"}])

    $scope.fields.assignee = test.who
    $scope.fields.user = test.user1
    $scope.form = {$valid: true}
    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith({assignee: test.who, user: test.user1})

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('AssignModalController.refreshUserList', () ->
    usersForPartner = spyOnPromise($q, $scope, UserService, 'fetchInPartner')

    $controller('AssignModalController', {$scope: $scope, $uibModalInstance: modalInstance, title: "Title", prompt: "OK?", partners: [test.moh, test.who]})

    expect($scope.users).toEqual([{id: null, name: "-- Anyone --"}])

    $scope.refreshUserList()
    usersForPartner.resolve([test.user1])

    expect($scope.users).toEqual([{id: null, name: "-- Anyone --"}, test.user1])
    expect(UserService.fetchInPartner).toHaveBeenCalledWith(test.moh, false)
  )

  it('ComposeModalController', () ->
    $controller('ComposeModalController', {$scope: $scope, $uibModalInstance: modalInstance, title: "Title", initial: "this..."})

    expect($scope.fields.urn).toEqual({scheme: 'tel', path: ""})
    expect($scope.fields.text).toEqual({val: "this..."})

    $scope.fields.text.val = "hello"
    $scope.fields.urn.scheme = "twitter"
    $scope.fields.urn.path = "12345"
    $scope.form = {$valid: true}
    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith({text: "hello", urn: {scheme: 'twitter', path: '12345', urn: 'twitter:12345'}})

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('ConfirmModalController', () ->
    $controller('ConfirmModalController', {$scope: $scope, $uibModalInstance: modalInstance, prompt: "Prompt", style: null})

    expect($scope.style).toEqual('primary')

    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith(true)

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('EditModalController', () ->
    $controller('EditModalController', {$scope: $scope, $uibModalInstance: modalInstance, title: "Title", initial: "this...", maxLength: 10})

    expect($scope.fields.text).toEqual({val: "this...", maxLength: 10})

    $scope.fields.text.val = "edited"
    $scope.form = {$valid: true}
    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith("edited")

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('FaqModalController', () ->
    fetchAllLanguages = spyOnPromise($q, $scope, FaqService, 'fetchAllLanguages')
    fetchLabels = spyOnPromise($q, $scope, LabelService, 'fetchAll')

    $controller('FaqModalController', {$scope: $scope, $uibModalInstance: modalInstance, title: "Title", translation: test.translation1, faq: test.faq1, isFaq: false})

    $scope.init()

    expect($scope.fields.question).toEqual({val: "Is ek swanger"})
    expect($scope.fields.answer).toEqual({val: "ja"})
    expect($scope.fields.parent).toEqual({val: 401})
    expect($scope.fields.language).toEqual({val: test.language2})
    expect($scope.fields.labels).toEqual({val: ''})
    expect($scope.fields.id).toEqual({val: 601})


    $scope.fields.question.val = "this is a question"
    $scope.fields.answer.val = "this is an answer"
    $scope.fields.parent.val = null
    $scope.fields.language.val = test.language1
    $scope.fields.labels.val = ''
    $scope.fields.id.val = null
    $scope.form = {$valid: true}
    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith({question: "this is a question", answer: "this is an answer", parent: null, language: test.language1.code, labels: '', id: null})

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('LabelModalController', () ->
    $controller('LabelModalController', {$scope: $scope, $uibModalInstance: modalInstance, title: "Title", prompt: "this...", labels: [test.tea, test.coffee], initial: [test.tea]})

    expect($scope.selection).toEqual([{label: test.tea, selected: true}, {label: test.coffee, selected: false}])

    $scope.selection[0].selected = false
    $scope.selection[1].selected = true
    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith([test.coffee])

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('MessageHistoryModalController', () ->
    fetchHistory = spyOnPromise($q, $scope, MessageService, 'fetchHistory')

    $controller('MessageHistoryModalController', {$scope: $scope, $uibModalInstance: modalInstance, message: test.msg1})

    fetchHistory.resolve([{action: "A", created_by: test.user1}])

    expect($scope.actions).toEqual([{action: "A", created_by: test.user1}])

    $scope.close()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('NewCaseModalController', () ->
    $controller('NewCaseModalController', {$scope: $scope, $uibModalInstance: modalInstance, summaryInitial: "Hello", summaryMaxLength: 10, contact: test.ann, partners: [test.moh, test.who]})

    expect($scope.fields.summary).toEqual({val: "Hello", maxLength: 10})
    expect($scope.fields.assignee).toEqual({val: test.moh})
    expect($scope.fields.user).toEqual({val: {id: null, name: "-- Anyone --"}})
    expect($scope.partners).toEqual([test.moh, test.who])
    expect($scope.users).toEqual([{id: null, name: "-- Anyone --"}])

    $scope.fields.summary.val = "Interesting"
    $scope.fields.assignee.val = test.who
    $scope.fields.user.val = test.user1
    $scope.form = {$valid: true}
    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith({summary: "Interesting", assignee: test.who, user: test.user1})

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('NewCaseModalController.refreshUserList', () ->
    usersForPartner = spyOnPromise($q, $scope, UserService, 'fetchInPartner')

    $controller('NewCaseModalController', {$scope: $scope, $uibModalInstance: modalInstance, summaryInitial: "Hello", summaryMaxLength: 10, contact: test.ann, partners: [test.moh, test.who]})

    expect($scope.users).toEqual([{id: null, name: "-- Anyone --"}])

    $scope.refreshUserList()
    usersForPartner.resolve([test.user1])

    expect($scope.users).toEqual([{id: null, name: "-- Anyone --"}, test.user1])
    expect(UserService.fetchInPartner).toHaveBeenCalledWith(test.moh, false)
  )

  it('NoteModalController', () ->
    $controller('NoteModalController', {$scope: $scope, $uibModalInstance: modalInstance, title: "Title", prompt: "this...", style: null, maxLength: 10})

    expect($scope.style).toEqual('primary')
    expect($scope.fields.note).toEqual({val: "", maxLength: 10})

    $scope.fields.note.val = "note"
    $scope.form = {$valid: true}
    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith("note")

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('ReplyModalController', () ->
    $controller('ReplyModalController', {$scope: $scope, $uibModalInstance: modalInstance, selection: null})

    expect($scope.fields.text).toEqual({val: ""})

    $scope.form = {$valid: true}
    $scope.ok()

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )
)
