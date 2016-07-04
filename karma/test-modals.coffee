# Unit tests for our Angular modal controllers (controllers listed A-Z)

describe('modals:', () ->
  $controller = null
  $rootScope = null
  $q = null
  MessageService = null

  $scope = null
  modalInstance = null
  test = null

  beforeEach(() ->
    module('cases')

    inject((_$controller_, _$rootScope_, _$q_, _MessageService_) ->
      $controller = _$controller_
      $rootScope = _$rootScope_
      $q = _$q_
      MessageService = _MessageService_
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

      msg1: {id: 501, text: "Hello"}
    }
  )

  it('AssignModalController', () ->
    $controller('AssignModalController', {$scope: $scope, $uibModalInstance: modalInstance, title: "Title", prompt: "OK?", partners: [test.moh, test.who]})

    expect($scope.fields.assignee).toEqual(test.moh)

    $scope.fields.assignee = test.who
    $scope.form = {$valid: true}
    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith(test.who)

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )

  it('ComposeModalController', () ->
    $controller('ComposeModalController', {$scope: $scope, $uibModalInstance: modalInstance, title: "Title", initial: "this...", maxLength: 10})

    expect($scope.fields.urn).toEqual({scheme: 'tel', path: ""})
    expect($scope.fields.text).toEqual({val: "this...", maxLength: 10})

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
    $controller('NewCaseModalController', {$scope: $scope, $uibModalInstance: modalInstance, summaryInitial: "Hello", summaryMaxLength: 10, partners: [test.moh, test.who]})

    expect($scope.fields.summary).toEqual({val: "Hello", maxLength: 10})
    expect($scope.fields.assignee).toEqual({val: test.moh})

    $scope.fields.summary.val = "Interesting"
    $scope.fields.assignee.val = test.who
    $scope.form = {$valid: true}
    $scope.ok()

    expect(modalInstance.close).toHaveBeenCalledWith({summary: "Interesting", assignee: test.who})

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
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
    $controller('ReplyModalController', {$scope: $scope, $uibModalInstance: modalInstance, maxLength: 10})

    expect($scope.fields.text).toEqual({val: "", maxLength: 10})

    $scope.form = {$valid: true}
    $scope.ok()

    $scope.cancel()

    expect(modalInstance.dismiss).toHaveBeenCalledWith(false)
  )
)
