// Те же команды wrapper/отчёта, что локально и в GitHub Actions.
// Статусы: упавшие тесты → UNSTABLE; ошибка компиляции / нет результатов / 0 тестов → FAILURE.
pipeline {
    agent { label 'java' }

    parameters {
        choice(name: 'BROWSER', choices: ['chrome', 'firefox'], description: 'browser for Selenide')
        booleanParam(name: 'HEADLESS', defaultValue: true, description: 'headless')
        string(name: 'BASE_URL', defaultValue: 'https://github.com', description: 'Selenide baseUrl')
        string(name: 'TESTS', defaultValue: '', description: 'gradle --tests filter (empty = all)')
        booleanParam(name: 'NO_SANDBOX', defaultValue: false,
            description: 'Chrome --no-sandbox ONLY for root/docker agents; deliberately OFF by default (not a copy of the GHA setting)')
        string(name: 'REMOTE_URL', defaultValue: 'https://user1:1234@selenoid.qa.guru/wd/hub',
            description: 'remote WebDriver (course Selenoid, shared guest creds — same as in the course demo repo; empty = local browser attempt)')
        string(name: 'BROWSER_VERSION', defaultValue: '',
            description: 'grid browserVersion capability (empty = any registered version)')
    }

    options { timestamps(); disableConcurrentBuilds(); buildDiscarder(logRotator(numToKeepStr: '20')) }

    environment { CI_NAME = 'Jenkins' }

    stages {
        stage('Versions') {
            steps {
                sh '''#!/bin/bash
                  java -version 2>&1 | head -1
                  node -v; npm -v
                  (python3 --version || echo "PYTHON3: NOT FOUND")
                  (google-chrome --version || chromium --version || chromium-browser --version || echo "CHROME: NOT FOUND")
                  (chromedriver --version || echo "CHROMEDRIVER: NOT FOUND")'''
            }
        }
        stage('Compile') {
            steps { sh './gradlew --no-daemon --console=plain compileTestJava' }
        }
        stage('UI tests') {
            steps {
                script {
                    def filter  = params.TESTS?.trim() ? "--tests '${params.TESTS.trim()}'" : ''
                    def sandbox = params.NO_SANDBOX ? '-DnoSandbox=true' : ''
                    def remote  = params.REMOTE_URL?.trim() ? "-Dremote='${params.REMOTE_URL.trim()}'" : ''
                    def bver    = params.BROWSER_VERSION?.trim() ? "-DbrowserVersion=${params.BROWSER_VERSION.trim()}" : ''
                    env.TEST_RC = sh(returnStatus: true, script: """
                        ./gradlew --no-daemon --console=plain test \
                          -Dbrowser=${params.BROWSER} -Dheadless=${params.HEADLESS} \
                          -DbaseUrl=${params.BASE_URL} ${sandbox} ${remote} ${bver} ${filter}""")
                }
            }
        }
        stage('Require test results') {
            steps {
                sh '''#!/bin/bash
                  total=$(grep -ho 'tests="[0-9]*"' build/test-results/test/*.xml 2>/dev/null | cut -d'"' -f2 | awk '{s+=$1} END {print s+0}')
                  echo "JUnit tests total: $total"
                  [ "$total" -gt 0 ] || { echo "No test results: build error or 0 tests — not success"; exit 1; }'''
            }
        }
        stage('Generate Allure report') {
            steps {
                sh '''#!/bin/bash
                  if [ -n "$(ls -A allure-results 2>/dev/null)" ]; then
                    npx --yes allure@3.33.0 generate allure-results -o allure-report
                  else
                    echo "No allure-results — report skipped (status decided by earlier stages)"
                  fi'''
            }
        }
    }

    post {
        always {
            script {
                if (env.TEST_RC != '0' && currentBuild.currentResult == 'SUCCESS') {
                    currentBuild.result = 'UNSTABLE'   // тесты вернули не-0, но junit ещё не пометил
                }
            }
            junit testResults: 'build/test-results/test/*.xml', allowEmptyResults: true, keepLongStdio: true
            archiveArtifacts artifacts: 'allure-results/**', allowEmptyArchive: true, defaultExcludes: false
            archiveArtifacts artifacts: 'allure-report/**', allowEmptyArchive: true
            script {
                def status = currentBuild.currentResult == 'SUCCESS' ? 'success'
                           : currentBuild.currentResult == 'ABORTED' ? 'cancelled' : 'failure'
                try {
                    withCredentials([string(credentialsId: 'telegram-bot-token', variable: 'TELEGRAM_BOT_TOKEN'),
                                     string(credentialsId: 'telegram-chat-id', variable: 'TELEGRAM_CHAT_ID')]) {
                        def envLine = "JOB_STATUS='${status}' PROJECT='${env.JOB_NAME}' WORKFLOW_NAME='Jenkins pipeline' " +
                            "RUN_BRANCH='${env.GIT_BRANCH ?: 'vodin_homework'}' RUN_SHA='${env.GIT_COMMIT ?: ''}' " +
                            "RUN_EVENT='jenkins' RUN_URL='${env.BUILD_URL}' CI_NAME='Jenkins' " +
                            "TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID"
                        def py = sh(returnStatus: true, script: 'command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1')
                        if (py == 0) {
                            def pyBin = sh(returnStdout: true, script: 'command -v python3 || command -v python').trim()
                            sh "${envLine} ${pyBin} scripts/ci_notify.py"
                        } else {
                            // java-агенты курса без python3 — тот же скрипт внутри лёгкого контейнера
                            docker.image('python:3.12-slim').inside('-u root') { sh "${envLine} python scripts/ci_notify.py" }
                        }
                    }
                } catch (e) {
                    // нет credentials или сеть/Telegram легли — статус прогона НЕ трогаем
                    echo "notify skipped/failed: ${e.message?.take(150)}"
                }
            }
        }
    }
}