module.exports = (config) ->
  config.set

    # base path that will be used to resolve all patterns (eg. files, exclude)
    basePath: ''

    # frameworks to use
    # available frameworks: https://npmjs.org/browse/keyword/karma-adapter
    frameworks: ['jasmine']

    # list of files / patterns to load in the browser
    files: [
      # dependencies
      'static/js/angular-1.4.14/angular.min.js',
      'static/js/angular-1.4.14/angular-animate.min.js',
      'static/js/angular-1.4.14/angular-sanitize.min.js',
      'static/js/angular-1.4.14/angular-mocks.js',
      'static/js/ng-infinite-scroll.min.js',
      'static/js/raven.min.js',
      'static/js/select.min.js',
      'static/js/ui-bootstrap-tpls-1.3.3.min.js',
      'static/js/libphonenumber.min.js',

      # templates
      'static/templates/**/*.html',
      'karma/templates/**/*.html',

      # the code we are testing
      'static/coffee/*.coffee',

      # our test files
      'karma/helpers.coffee',
      'karma/test-controllers.coffee',
      'karma/test-services.coffee',
      'karma/test-filters.coffee',
      'karma/test-directives.coffee',
      'karma/test-modals.coffee',
      'karma/test-utils.coffee',
      'karma/test-directives.coffee'
    ]

    # list of files to exclude
    exclude: [
    ]

    # preprocess matching files before serving them to the browser
    # available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
    preprocessors: {
      '**/*.coffee': ['coffee'],
      'static/**/*.coffee': ['coverage']
      'static/templates/**/*.html': ['ng-html2js']
      'karma/templates/**/*.html': ['ng-html2js']
    }

    # this makes sure that we get coffeescript line numbers instead
    # of the line number from the transpiled
    coffeePreprocessor:
      options:
        bare: true
        sourceMap: true
      transformPath: (path) ->
        path.replace /\.js$/, '.coffee'

    ngHtml2JsPreprocessor:
      stripPrefix: 'static/'
      prependPrefix: '/sitestatic/'
      moduleName: 'templates'

    # test results reporter to use
    # possible values: 'dots', 'progress'
    # available reporters: https://npmjs.org/browse/keyword/karma-reporter
    reporters: ['progress', 'coverage']

    coverageReporter:
      type: 'html'
      dir: 'js-coverage/'

    # web server port
    port: 9876

    # enable / disable colors in the output (reporters and logs)
    colors: true

    # level of logging
    logLevel: config.LOG_INFO

    # enable / disable watching file and executing tests whenever any file changes
    autoWatch: false

    # start these browsers
    # available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
    browsers: ['PhantomJS']

    # Continuous Integration mode
    # if true, Karma captures browsers, runs the tests and exits
    singleRun: false
