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
                  (chromedriver --version || echo "CHROMEDRIVER: NOT FOUND")
                  ( echo "DIAG selenoid:"
                    getent hosts selenoid.qa.guru || echo "DIAG: NO DNS for selenoid.qa.guru"
                    curl -s -o /dev/null -w "DIAG status GET: %{http_code}\n" -u user1:1234 -m 10 https://selenoid.qa.guru/status
                    RESP=$(curl -s -m 30 -u user1:1234 -X POST -H 'Content-Type: application/json' -d '{"capabilities":{"alwaysMatch":{"browserName":"chrome"}}}' https://selenoid.qa.guru/wd/hub/session)
                    echo "DIAG session resp: $(echo "$RESP" | head -c 300)"
                    SID=$(echo "$RESP" | sed -n 's/.*"sessionId":"\\([^"]*\\)".*/\\1/p')
                    test -n "$SID" && curl -s -o /dev/null -w "DIAG session DELETE: %{http_code}\n" -u user1:1234 -X DELETE -m 10 "https://selenoid.qa.guru/wd/hub/session/$SID"
                    RESP2=$(curl -s -m 30 -u user1:1234 -X POST -H 'Content-Type: application/json' -d '{"capabilities":{"alwaysMatch":{"browserName":"chrome","goog:chromeOptions":{"args":["--headless=new","--window-size=1920,1080"],"extensions":[]}}}}' https://selenoid.qa.guru/wd/hub/session)
                    echo "DIAG session(headless) resp: $(echo "$RESP2" | head -c 300)"
                    SID2=$(echo "$RESP2" | sed -n 's/.*"sessionId":"\\([^"]*\\)".*/\\1/p')
                    test -n "$SID2" && curl -s -o /dev/null -w "DIAG session2 DELETE: %{http_code}\n" -u user1:1234 -X DELETE -m 10 "https://selenoid.qa.guru/wd/hub/session/$SID2"
                    env | grep -iE 'java_tool_options|_java_options|proxy' || echo "DIAG: no proxy/JAVA_TOOL_OPTIONS in env" ) || true'''
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
                        sh """#!/bin/bash
                          JOB_STATUS='${status}' PROJECT='${env.JOB_NAME}' WORKFLOW_NAME='Jenkins pipeline' \
                          RUN_BRANCH='${env.GIT_BRANCH ?: 'vodin_homework'}' RUN_SHA='${env.GIT_COMMIT ?: ''}' \
                          RUN_EVENT='jenkins' RUN_URL='${env.BUILD_URL}' CI_NAME='Jenkins' \
                          TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID python3 scripts/ci_notify.py"""
                    }
                } catch (e) {
                    // нет credentials или сеть/Telegram легли — статус прогона НЕ трогаем
                    echo "notify skipped/failed: ${e.message?.take(150)}"
                }
            }
        }
    }
}