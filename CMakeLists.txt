cmake_minimum_required(VERSION 3.24)

project(proton-vpn-kde VERSION 0.11.2 LANGUAGES CXX)
set(PROJECT_HOMEPAGE_URL "https://github.com/uglyegg/proton-vpn-kde")

option(
    PROTON_VPN_KDE_ENABLE_SUPPORT_REPORT_SUBMISSION
    "Allow direct support-report submission to Proton's production API"
    OFF
)
option(
    PROTON_VPN_KDE_ENABLE_CRASH_REPORT_SUBMISSION
    "Allow anonymous crash-report submission to Proton's production API"
    OFF
)

find_package(ECM 6.0 REQUIRED NO_MODULE)
list(APPEND CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
include(KDEInstallDirs6)
include(CTest)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 6.8 REQUIRED COMPONENTS
    Core
    DBus
    Gui
    Network
    Qml
    Quick
    QuickControls2
    LinguistTools
    Widgets
)
if(EXISTS "/usr/bin/python3" AND NOT DEFINED Python3_EXECUTABLE)
    # Distro packages for Proton's core are installed for the system Python.
    # Avoid accidentally binding the service to a user's pyenv/virtualenv.
    set(Python3_EXECUTABLE "/usr/bin/python3" CACHE FILEPATH
        "Python interpreter used by the installed backend")
endif()
find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)

# KStatusNotifierItem is deliberately optional at configure time so the Qt and
# D-Bus boundary can be developed on systems without KDE development headers.
# Fedora/Plasma production builds should install kf6-kstatusnotifieritem-devel.
find_package(KF6StatusNotifierItem QUIET)
find_package(KF6Config 6.0 REQUIRED)
find_package(KF6CoreAddons 6.0 REQUIRED)
find_package(KF6GlobalAccel 6.0 REQUIRED)
find_package(KF6KCMUtils 6.0 REQUIRED)
find_package(KF6Notifications 6.0 REQUIRED)
find_package(KF6Runner 6.0 REQUIRED)
find_package(KF6Service 6.0 REQUIRED)
find_package(OpenSSL 3.0 REQUIRED COMPONENTS Crypto)

qt_standard_project_setup(REQUIRES 6.8)

file(GLOB PROTON_VPN_KDE_TS_FILES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/translations/proton-vpn-kde_*.ts"
)
set(PROTON_VPN_KDE_BUILD_TRANSLATIONS_DIR
    "${CMAKE_CURRENT_BINARY_DIR}/translations")
qt_add_lrelease(
    LRELEASE_TARGET proton-vpn-kde-translations
    TS_FILES ${PROTON_VPN_KDE_TS_FILES}
    QM_OUTPUT_DIRECTORY "${PROTON_VPN_KDE_BUILD_TRANSLATIONS_DIR}"
    QM_FILES_OUTPUT_VARIABLE PROTON_VPN_KDE_QM_FILES
    OPTIONS -compress
)

function(proton_vpn_kde_enable_translations target)
    target_compile_definitions(${target} PRIVATE
        PROTON_VPN_KDE_BUILD_TRANSLATIONS_DIR="${PROTON_VPN_KDE_BUILD_TRANSLATIONS_DIR}"
    )
    add_dependencies(${target} proton-vpn-kde-translations)
endfunction()

function(proton_vpn_kde_enable_backend_identity target)
    target_compile_definitions(${target} PRIVATE
        PROTON_VPN_KDE_BACKEND_EXECUTABLE_PATH="${CMAKE_INSTALL_FULL_BINDIR}/proton-vpn-kde-backend"
        PROTON_VPN_KDE_BACKEND_UNIT_PATH="${KDE_INSTALL_FULL_SYSTEMDUSERUNITDIR}/proton-vpn-kde-backend.service"
    )
endfunction()

qt_add_executable(proton-vpn-kde
    src/AgentControl.cpp
    src/AgentControl.h
    src/AppIcon.cpp
    src/AppIcon.h
    src/BackendCallPolicy.h
    src/BackendIdentity.cpp
    src/BackendIdentity.h
    src/ClientRegistrationState.h
    src/AppSettings.cpp
    src/AppSettings.h
    src/CustomDnsModel.cpp
    src/CustomDnsModel.h
    src/ConnectionAction.h
    src/InstalledApplicationModel.cpp
    src/InstalledApplicationModel.h
    src/SecretTransport.cpp
    src/SecretTransport.h
    src/TranslationLoader.cpp
    src/TranslationLoader.h
    src/SplitTunnelingModel.cpp
    src/SplitTunnelingModel.h
    src/main.cpp
    src/LocationModels.cpp
    src/LocationModels.h
    src/RunnerActionRequest.cpp
    src/RunnerActionRequest.h
    src/UpdateChannel.cpp
    src/UpdateChannel.h
    src/VpnController.cpp
    src/VpnController.h
    src/VpnConnectionController.h
    src/VpnSettingsModel.cpp
    src/VpnSettingsModel.h
)
proton_vpn_kde_enable_translations(proton-vpn-kde)
proton_vpn_kde_enable_backend_identity(proton-vpn-kde)

qt_add_executable(proton-vpn-kde-agent
    src/AgentControl.cpp
    src/AgentControl.h
    src/AgentVpnClient.cpp
    src/AgentVpnClient.h
    src/AppIcon.cpp
    src/AppIcon.h
    src/AppSettings.cpp
    src/AppSettings.h
    src/BackendCallPolicy.h
    src/BackendIdentity.cpp
    src/BackendIdentity.h
    src/ConnectionAction.h
    src/NotificationIntegration.cpp
    src/NotificationIntegration.h
    src/RunnerActionRequest.cpp
    src/RunnerActionRequest.h
    src/ShortcutIntegration.cpp
    src/ShortcutIntegration.h
    src/TranslationLoader.cpp
    src/TranslationLoader.h
    src/TrayIntegration.cpp
    src/TrayIntegration.h
    src/VpnConnectionController.h
    src/agent_main.cpp
)
proton_vpn_kde_enable_translations(proton-vpn-kde-agent)
proton_vpn_kde_enable_backend_identity(proton-vpn-kde-agent)

qt_add_resources(proton-vpn-kde "plasma-vpn-app-icon"
    PREFIX "/"
    FILES
        data/plasma-vpn.svg
        data/plasma-vpn-light.svg
        data/plasma-vpn-dark.svg
)
qt_add_resources(proton-vpn-kde-agent "plasma-vpn-agent-icon"
    PREFIX "/"
    FILES
        data/plasma-vpn.svg
        data/plasma-vpn-light.svg
        data/plasma-vpn-dark.svg
)

qt_add_qml_module(proton-vpn-kde
    URI Proton.VPN.KDE
    VERSION 1.0
    NO_IMPORT_SCAN
    QML_FILES
        qml/Main.qml
        qml/AccountPage.qml
        qml/AboutPage.qml
        qml/CustomDnsPage.qml
        qml/CountryPage.qml
        qml/DetailRow.qml
        qml/LocationsPage.qml
        qml/OverviewPage.qml
        qml/PageHeader.qml
        qml/PlasmaListItem.qml
        qml/ReportIssuePage.qml
        qml/ReleaseNotesPage.qml
        qml/SectionCard.qml
        qml/ServerCapabilitySelector.qml
        qml/ServersPage.qml
        qml/SettingsPage.qml
        qml/SignInPage.qml
        qml/SplitTunnelingPage.qml
)

target_link_libraries(proton-vpn-kde PRIVATE
    Qt6::Core
    Qt6::DBus
    Qt6::Gui
    Qt6::Network
    Qt6::Qml
    Qt6::Quick
    Qt6::QuickControls2
    Qt6::Widgets
    KF6::ConfigCore
    KF6::CoreAddons
    KF6::Service
    OpenSSL::Crypto
)

target_compile_options(proton-vpn-kde PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
)
target_compile_definitions(proton-vpn-kde PRIVATE _GNU_SOURCE)
target_compile_definitions(
    proton-vpn-kde PRIVATE
    PROTON_VPN_KDE_VERSION="${PROJECT_VERSION}"
    PROTON_VPN_KDE_SUPPORT_REPORT_SUBMISSION_ENABLED=$<BOOL:${PROTON_VPN_KDE_ENABLE_SUPPORT_REPORT_SUBMISSION}>
    PROTON_VPN_KDE_CRASH_REPORT_SUBMISSION_ENABLED=$<BOOL:${PROTON_VPN_KDE_ENABLE_CRASH_REPORT_SUBMISSION}>
)

target_link_libraries(proton-vpn-kde-agent PRIVATE
    Qt6::Core
    Qt6::DBus
    Qt6::Gui
    Qt6::Widgets
    KF6::ConfigCore
    KF6::CoreAddons
    KF6::GlobalAccel
    KF6::Notifications
)
target_compile_options(proton-vpn-kde-agent PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
)
target_compile_definitions(
    proton-vpn-kde-agent PRIVATE
    PROTON_VPN_KDE_VERSION="${PROJECT_VERSION}"
)

if(TARGET KF6::StatusNotifierItem)
    target_link_libraries(proton-vpn-kde-agent PRIVATE KF6::StatusNotifierItem)
    target_compile_definitions(proton-vpn-kde-agent PRIVATE HAVE_KSTATUSNOTIFIERITEM=1)
endif()

add_library(proton-vpn-kde-runner MODULE
    runner/ProtonVpnRunner.cpp
    runner/ProtonVpnRunner.h
    runner/RunnerCommand.cpp
    runner/RunnerCommand.h
    src/TranslationLoader.cpp
    src/TranslationLoader.h
)
target_include_directories(proton-vpn-kde-runner PRIVATE src)
configure_file(
    runner/proton-vpn-kde-runner.json.in
    ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-runner.json
    @ONLY
)
set_target_properties(proton-vpn-kde-runner PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib/kf6/krunner"
    PREFIX ""
)
target_include_directories(proton-vpn-kde-runner PRIVATE
    runner
    src
    ${CMAKE_CURRENT_BINARY_DIR}
)
proton_vpn_kde_enable_translations(proton-vpn-kde-runner)
target_link_libraries(proton-vpn-kde-runner PRIVATE
    Qt6::Core
    Qt6::DBus
    KF6::CoreAddons
    KF6::Runner
)
target_compile_options(proton-vpn-kde-runner PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
)

if(BUILD_TESTING)
    find_package(Qt6 6.8 REQUIRED COMPONENTS Test)
endif()
add_subdirectory(kcm)

if(BUILD_TESTING)
    find_program(DBUS_RUN_SESSION_EXECUTABLE dbus-run-session)
    qt_add_executable(backend-call-policy-tests
        tests/BackendCallPolicyTest.cpp
        src/BackendCallPolicy.h
        src/ClientRegistrationState.h
    )
    target_include_directories(backend-call-policy-tests PRIVATE src)
    target_link_libraries(backend-call-policy-tests PRIVATE
        Qt6::Core
        Qt6::DBus
        Qt6::Test
    )
    target_compile_options(backend-call-policy-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME backend-call-policy-tests COMMAND backend-call-policy-tests)

    qt_add_executable(backend-identity-tests
        tests/BackendIdentityTest.cpp
        src/BackendIdentity.cpp
        src/BackendIdentity.h
    )
    target_include_directories(backend-identity-tests PRIVATE src)
    target_link_libraries(backend-identity-tests PRIVATE
        Qt6::Core
        Qt6::DBus
        Qt6::Test
    )
    target_compile_options(backend-identity-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME backend-identity-tests COMMAND backend-identity-tests)

    qt_add_executable(agent-vpn-client-tests
        tests/AgentVpnClientTest.cpp
        src/AgentVpnClient.cpp
        src/AgentVpnClient.h
        src/BackendCallPolicy.h
        src/BackendIdentity.cpp
        src/BackendIdentity.h
        src/ConnectionAction.h
        src/VpnConnectionController.h
    )
    target_include_directories(agent-vpn-client-tests PRIVATE src)
    target_link_libraries(agent-vpn-client-tests PRIVATE
        Qt6::Core
        Qt6::DBus
        Qt6::Test
    )
    target_compile_options(agent-vpn-client-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    proton_vpn_kde_enable_backend_identity(agent-vpn-client-tests)
    if(DBUS_RUN_SESSION_EXECUTABLE)
        add_test(
            NAME agent-vpn-client-tests
            COMMAND ${DBUS_RUN_SESSION_EXECUTABLE} --
                $<TARGET_FILE:agent-vpn-client-tests>
        )
    else()
        add_test(NAME agent-vpn-client-tests COMMAND agent-vpn-client-tests)
    endif()

    qt_add_executable(grouped-navigation-tests
        tests/GroupedNavigationTest.cpp
        src/BackendCallPolicy.h
        src/BackendIdentity.cpp
        src/BackendIdentity.h
        src/ClientRegistrationState.h
        src/CustomDnsModel.cpp
        src/CustomDnsModel.h
        src/InstalledApplicationModel.cpp
        src/InstalledApplicationModel.h
        src/LocationModels.cpp
        src/LocationModels.h
        src/SecretTransport.cpp
        src/SecretTransport.h
        src/SplitTunnelingModel.cpp
        src/SplitTunnelingModel.h
        src/VpnController.cpp
        src/VpnController.h
        src/VpnConnectionController.h
        src/VpnSettingsModel.cpp
        src/VpnSettingsModel.h
    )
    target_include_directories(grouped-navigation-tests PRIVATE src)
    target_link_libraries(grouped-navigation-tests PRIVATE
        Qt6::Core
        Qt6::DBus
        Qt6::Gui
        Qt6::Network
        Qt6::Test
        Qt6::Widgets
        KF6::CoreAddons
        KF6::Service
        OpenSSL::Crypto
    )
    target_compile_definitions(
        grouped-navigation-tests PRIVATE
        _GNU_SOURCE
        PROTON_VPN_KDE_SUPPORT_REPORT_SUBMISSION_ENABLED=$<BOOL:${PROTON_VPN_KDE_ENABLE_SUPPORT_REPORT_SUBMISSION}>
        PROTON_VPN_KDE_CRASH_REPORT_SUBMISSION_ENABLED=$<BOOL:${PROTON_VPN_KDE_ENABLE_CRASH_REPORT_SUBMISSION}>
    )
    target_compile_options(grouped-navigation-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    proton_vpn_kde_enable_backend_identity(grouped-navigation-tests)
    if(DBUS_RUN_SESSION_EXECUTABLE)
        add_test(
            NAME grouped-navigation-tests
            COMMAND ${DBUS_RUN_SESSION_EXECUTABLE} --
                $<TARGET_FILE:grouped-navigation-tests>
        )
    else()
        add_test(NAME grouped-navigation-tests COMMAND grouped-navigation-tests)
    endif()
    set_tests_properties(grouped-navigation-tests PROPERTIES
        ENVIRONMENT
            "QT_QPA_PLATFORM=offscreen;XDG_DATA_DIRS=${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data"
        TIMEOUT 15
    )

    qt_add_executable(connection-action-tests
        tests/ConnectionActionTest.cpp
        src/ConnectionAction.h
    )
    target_include_directories(connection-action-tests PRIVATE src)
    target_link_libraries(connection-action-tests PRIVATE Qt6::Core Qt6::Test)
    target_compile_options(connection-action-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME connection-action-tests COMMAND connection-action-tests)

    qt_add_executable(location-model-tests
        tests/LocationModelsTest.cpp
        src/LocationModels.cpp
        src/LocationModels.h
    )
    target_include_directories(location-model-tests PRIVATE src)
    target_link_libraries(location-model-tests PRIVATE Qt6::Core Qt6::Test)
    target_compile_options(location-model-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME location-model-tests COMMAND location-model-tests)

    qt_add_executable(app-settings-tests
        tests/AppSettingsTest.cpp
        src/AppSettings.cpp
        src/AppSettings.h
    )
    target_include_directories(app-settings-tests PRIVATE src)
    target_link_libraries(app-settings-tests PRIVATE
        Qt6::Core
        Qt6::Test
        KF6::ConfigCore
    )
    target_compile_options(app-settings-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    if(DBUS_RUN_SESSION_EXECUTABLE)
        add_test(
            NAME app-settings-tests
            COMMAND ${DBUS_RUN_SESSION_EXECUTABLE} --
                $<TARGET_FILE:app-settings-tests>
        )
    else()
    add_test(NAME app-settings-tests COMMAND app-settings-tests)
    endif()

    qt_add_executable(app-icon-tests
        tests/AppIconTest.cpp
        src/AppIcon.cpp
        src/AppIcon.h
    )
    target_include_directories(app-icon-tests PRIVATE src)
    target_link_libraries(app-icon-tests PRIVATE
        Qt6::Core
        Qt6::Gui
        Qt6::Test
        Qt6::Widgets
    )
    target_compile_options(app-icon-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    qt_add_resources(app-icon-tests "plasma-vpn-test-icon"
        PREFIX "/"
        FILES
            data/plasma-vpn.svg
            data/plasma-vpn-light.svg
            data/plasma-vpn-dark.svg
    )
    add_test(NAME app-icon-tests COMMAND app-icon-tests)
    set_tests_properties(app-icon-tests PROPERTIES
        ENVIRONMENT "QT_QPA_PLATFORM=offscreen"
    )

    qt_add_executable(update-channel-tests
        tests/UpdateChannelTest.cpp
        src/UpdateChannel.cpp
        src/UpdateChannel.h
    )
    target_include_directories(update-channel-tests PRIVATE src)
    target_link_libraries(update-channel-tests PRIVATE
        Qt6::Core
        Qt6::Test
    )
    target_compile_options(update-channel-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME update-channel-tests COMMAND update-channel-tests)

    qt_add_executable(runner-command-tests
        tests/RunnerCommandTest.cpp
        runner/RunnerCommand.cpp
        runner/RunnerCommand.h
    )
    target_include_directories(runner-command-tests PRIVATE runner)
    target_link_libraries(runner-command-tests PRIVATE Qt6::Core Qt6::Test)
    target_compile_options(runner-command-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME runner-command-tests COMMAND runner-command-tests)

    qt_add_executable(runner-action-request-tests
        tests/RunnerActionRequestTest.cpp
        src/RunnerActionRequest.cpp
        src/RunnerActionRequest.h
    )
    target_include_directories(runner-action-request-tests PRIVATE src)
    target_link_libraries(runner-action-request-tests PRIVATE
        Qt6::Core
        Qt6::Test
    )
    target_compile_options(runner-action-request-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME runner-action-request-tests COMMAND runner-action-request-tests)

    qt_add_executable(control-center-control-tests
        tests/ControlCenterControlTest.cpp
        src/AgentControl.cpp
        src/AgentControl.h
        src/RunnerActionRequest.cpp
        src/RunnerActionRequest.h
    )
    target_include_directories(control-center-control-tests PRIVATE src)
    target_link_libraries(control-center-control-tests PRIVATE
        Qt6::Core
        Qt6::DBus
        Qt6::Gui
        Qt6::Test
    )
    target_compile_options(control-center-control-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME control-center-control-tests COMMAND control-center-control-tests)

    qt_add_executable(krunner-plugin-tests
        tests/ProtonVpnRunnerTest.cpp
    )
    target_link_libraries(krunner-plugin-tests PRIVATE
        Qt6::Core
        Qt6::DBus
        Qt6::Test
        KF6::Runner
    )
    krunner_configure_test(krunner-plugin-tests proton-vpn-kde-runner)
    if(DBUS_RUN_SESSION_EXECUTABLE)
        add_test(
            NAME krunner-plugin-tests
            COMMAND ${DBUS_RUN_SESSION_EXECUTABLE} --
                $<TARGET_FILE:krunner-plugin-tests>
        )
    else()
        add_test(NAME krunner-plugin-tests COMMAND krunner-plugin-tests)
    endif()

    qt_add_executable(vpn-settings-model-tests
        tests/VpnSettingsModelTest.cpp
        src/VpnSettingsModel.cpp
        src/VpnSettingsModel.h
    )
    target_include_directories(vpn-settings-model-tests PRIVATE src)
    target_link_libraries(vpn-settings-model-tests PRIVATE
        Qt6::Core
        Qt6::Test
    )
    target_compile_options(vpn-settings-model-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME vpn-settings-model-tests COMMAND vpn-settings-model-tests)

    qt_add_executable(split-tunneling-model-tests
        tests/SplitTunnelingModelTest.cpp
        src/SplitTunnelingModel.cpp
        src/SplitTunnelingModel.h
    )
    target_include_directories(split-tunneling-model-tests PRIVATE src)
    target_link_libraries(split-tunneling-model-tests PRIVATE
        Qt6::Core
        Qt6::Test
    )
    target_compile_options(split-tunneling-model-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME split-tunneling-model-tests COMMAND split-tunneling-model-tests)

    qt_add_executable(custom-dns-model-tests
        tests/CustomDnsModelTest.cpp
        src/CustomDnsModel.cpp
        src/CustomDnsModel.h
    )
    target_include_directories(custom-dns-model-tests PRIVATE src)
    target_link_libraries(custom-dns-model-tests PRIVATE
        Qt6::Core
        Qt6::Network
        Qt6::Test
    )
    target_compile_options(custom-dns-model-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME custom-dns-model-tests COMMAND custom-dns-model-tests)

    qt_add_executable(installed-application-model-tests
        tests/InstalledApplicationModelTest.cpp
        src/InstalledApplicationModel.cpp
        src/InstalledApplicationModel.h
    )
    target_include_directories(installed-application-model-tests PRIVATE src)
    target_link_libraries(installed-application-model-tests PRIVATE
        Qt6::Core
        Qt6::Test
        KF6::CoreAddons
        KF6::Service
    )
    target_compile_options(installed-application-model-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME installed-application-model-tests
        COMMAND installed-application-model-tests)

    qt_add_executable(secret-transport-tests
        tests/SecretTransportTest.cpp
        src/SecretTransport.cpp
        src/SecretTransport.h
    )
    target_include_directories(secret-transport-tests PRIVATE src)
    target_link_libraries(secret-transport-tests PRIVATE
        Qt6::Core
        Qt6::DBus
        Qt6::Test
        OpenSSL::Crypto
    )
    target_compile_definitions(secret-transport-tests PRIVATE _GNU_SOURCE)
    target_compile_options(secret-transport-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME secret-transport-tests COMMAND secret-transport-tests)

    qt_add_executable(translation-loader-tests
        tests/TranslationLoaderTest.cpp
        src/TranslationLoader.cpp
        src/TranslationLoader.h
    )
    target_include_directories(translation-loader-tests PRIVATE src)
    target_link_libraries(translation-loader-tests PRIVATE Qt6::Core Qt6::Test)
    proton_vpn_kde_enable_translations(translation-loader-tests)
    target_compile_options(translation-loader-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(NAME translation-loader-tests COMMAND translation-loader-tests)

    set(PROTON_VPN_KDE_TEST_DATA_DIR
        "${CMAKE_CURRENT_BINARY_DIR}/installed-translation-test-data")
    add_custom_target(installed-translation-test-data
        COMMAND ${CMAKE_COMMAND} -E make_directory
            "${PROTON_VPN_KDE_TEST_DATA_DIR}/proton-vpn-kde/translations"
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${PROTON_VPN_KDE_BUILD_TRANSLATIONS_DIR}/proton-vpn-kde_es_LA.qm"
            "${PROTON_VPN_KDE_TEST_DATA_DIR}/proton-vpn-kde/translations/"
        DEPENDS proton-vpn-kde-translations
    )
    qt_add_executable(installed-translation-loader-tests
        tests/TranslationLoaderTest.cpp
        src/TranslationLoader.cpp
        src/TranslationLoader.h
    )
    target_include_directories(installed-translation-loader-tests PRIVATE src)
    target_link_libraries(installed-translation-loader-tests PRIVATE
        Qt6::Core
        Qt6::Test
    )
    target_compile_definitions(installed-translation-loader-tests PRIVATE
        PROTON_VPN_KDE_BUILD_TRANSLATIONS_DIR="/nonexistent"
    )
    add_dependencies(installed-translation-loader-tests
        installed-translation-test-data)
    target_compile_options(installed-translation-loader-tests PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(
        NAME installed-translation-loader-tests
        COMMAND installed-translation-loader-tests
    )
    add_test(
        NAME qml-ui-hygiene
        COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/scripts/check-qml-ui-hygiene.sh
    )
    set_tests_properties(installed-translation-loader-tests PROPERTIES
        ENVIRONMENT "XDG_DATA_DIRS=${PROTON_VPN_KDE_TEST_DATA_DIR}"
    )

    qt_add_executable(secret-transport-vector
        tests/SecretTransportVector.cpp
        src/SecretTransport.cpp
        src/SecretTransport.h
    )
    target_include_directories(secret-transport-vector PRIVATE src)
    target_link_libraries(secret-transport-vector PRIVATE
        Qt6::Core
        Qt6::DBus
        OpenSSL::Crypto
    )
    target_compile_definitions(secret-transport-vector PRIVATE _GNU_SOURCE)
    target_compile_options(secret-transport-vector PRIVATE
        $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
    )
    add_test(
        NAME secret-transport-interop
        COMMAND ${CMAKE_COMMAND} -E env
            "PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}/backend"
            ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/scripts/test-secret-interop.py
            $<TARGET_FILE:secret-transport-vector>
    )

    add_test(
        NAME backend-tests
        COMMAND ${CMAKE_COMMAND} -E env
            "PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}/backend"
            ${Python3_EXECUTABLE} -m unittest discover
            -s ${CMAKE_CURRENT_SOURCE_DIR}/backend/tests -v
    )

    add_test(
        NAME api-core-overlay-tests
        COMMAND ${Python3_EXECUTABLE} -m unittest discover
            -s ${CMAKE_CURRENT_SOURCE_DIR}/packaging/fedora/api-core-overlay/tests
            -v
    )
    add_test(
        NAME release-metadata
        COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/scripts/check-release-metadata.sh
    )

    if(DBUS_RUN_SESSION_EXECUTABLE)
        file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data)
        file(MAKE_DIRECTORY
            ${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data/dbus-1/services)
        file(GENERATE
            OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data/dbus-1/services/quest.entropy.PlasmaVPN.ControlCenter.service
            CONTENT "[D-BUS Service]\nName=quest.entropy.PlasmaVPN.ControlCenter\nExec=$<TARGET_FILE:proton-vpn-kde> --show\n"
        )
        configure_file(
            tests/agent-session.conf.in
            ${CMAKE_CURRENT_BINARY_DIR}/agent-session.conf
            @ONLY
        )
        add_test(
            NAME auth-dbus-smoke
            COMMAND ${CMAKE_COMMAND} -E env
                "XDG_DATA_DIRS=${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data"
                ${DBUS_RUN_SESSION_EXECUTABLE} --
                    ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-auth-demo.sh
        )
        add_test(
            NAME backend-lifetime-smoke
            COMMAND ${CMAKE_COMMAND} -E env
                "XDG_DATA_DIRS=${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data"
                ${DBUS_RUN_SESSION_EXECUTABLE} --
                    ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-backend-lifetime.sh
        )
        add_test(
            NAME agent-lifetime-smoke
            COMMAND ${CMAKE_COMMAND} -E env
                "XDG_DATA_DIRS=${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data"
                ${DBUS_RUN_SESSION_EXECUTABLE} --
                    ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-agent-lifetime.sh
                    ${CMAKE_CURRENT_BINARY_DIR}
        )
        set_tests_properties(agent-lifetime-smoke PROPERTIES TIMEOUT 15)
        add_test(
            NAME control-center-activation-smoke
            COMMAND ${CMAKE_COMMAND} -E env
                "XDG_DATA_DIRS=${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data"
                "QT_QPA_PLATFORM=offscreen"
                "QT_QPA_PLATFORMTHEME=generic"
                "QT_ACCESSIBILITY=0"
                ${DBUS_RUN_SESSION_EXECUTABLE}
                    --config-file=${CMAKE_CURRENT_BINARY_DIR}/agent-session.conf
                    --
                    ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-control-center-activation.sh
                    ${CMAKE_CURRENT_BINARY_DIR}
        )
        set_tests_properties(control-center-activation-smoke PROPERTIES
            RUN_SERIAL TRUE
            TIMEOUT 20
        )
        add_test(
            NAME staged-install-smoke
            COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-staged-install.sh
                ${CMAKE_CURRENT_BINARY_DIR}
                ${CMAKE_INSTALL_FULL_BINDIR}
                ${CMAKE_INSTALL_FULL_LIBEXECDIR}
                ${CMAKE_INSTALL_FULL_DATADIR}
                ${KDE_INSTALL_FULL_SYSTEMDUSERUNITDIR}
        )
        add_test(
            NAME qml-diagnostics-smoke
            COMMAND ${CMAKE_COMMAND} -E env
                ${DBUS_RUN_SESSION_EXECUTABLE}
                    --config-file=${CMAKE_CURRENT_SOURCE_DIR}/tests/no-activation-session.conf
                    --
                    ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-qml-diagnostics.sh
                    ${CMAKE_CURRENT_BINARY_DIR}
        )
        set_tests_properties(qml-diagnostics-smoke PROPERTIES
            RUN_SERIAL TRUE
            TIMEOUT 25
        )
        add_test(
            NAME signed-out-startup-route-smoke
            COMMAND ${CMAKE_COMMAND} -E env
                ${DBUS_RUN_SESSION_EXECUTABLE}
                    --config-file=${CMAKE_CURRENT_SOURCE_DIR}/tests/no-activation-session.conf
                    --
                    ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-signed-out-route.sh
                    ${CMAKE_CURRENT_BINARY_DIR}
        )
        set_tests_properties(signed-out-startup-route-smoke PROPERTIES
            RUN_SERIAL TRUE
            TIMEOUT 15
        )
        add_test(
            NAME settings-route-preservation-smoke
            COMMAND ${CMAKE_COMMAND} -E env
                ${DBUS_RUN_SESSION_EXECUTABLE}
                    --config-file=${CMAKE_CURRENT_SOURCE_DIR}/tests/no-activation-session.conf
                    --
                    ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-settings-route.sh
                    ${CMAKE_CURRENT_BINARY_DIR}
        )
        set_tests_properties(settings-route-preservation-smoke PROPERTIES
            RUN_SERIAL TRUE
            TIMEOUT 15
        )
        add_test(
            NAME qml-layout-variants-smoke
            COMMAND ${CMAKE_COMMAND} -E env
                ${DBUS_RUN_SESSION_EXECUTABLE}
                    --config-file=${CMAKE_CURRENT_SOURCE_DIR}/tests/no-activation-session.conf
                    --
                    ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-qml-layout-variants.sh
                    ${CMAKE_CURRENT_BINARY_DIR}
        )
        set_tests_properties(qml-layout-variants-smoke PROPERTIES
            RUN_SERIAL TRUE
            TIMEOUT 45
        )
    endif()
endif()

configure_file(
    data/quest.entropy.PlasmaVPN.Backend.service.in
    ${CMAKE_CURRENT_BINARY_DIR}/quest.entropy.PlasmaVPN.Backend.service
    @ONLY
)
configure_file(
    data/proton-vpn-kde-backend.service.in
    ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-backend.service
    @ONLY
)
configure_file(
    data/quest.entropy.PlasmaVPN.Agent.service.in
    ${CMAKE_CURRENT_BINARY_DIR}/quest.entropy.PlasmaVPN.Agent.service
    @ONLY
)
configure_file(
    data/quest.entropy.PlasmaVPN.ControlCenter.service.in
    ${CMAKE_CURRENT_BINARY_DIR}/quest.entropy.PlasmaVPN.ControlCenter.service
    @ONLY
)
configure_file(
    data/proton-vpn-kde-agent.service.in
    ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-agent.service
    @ONLY
)
if(IS_ABSOLUTE "${CMAKE_INSTALL_LIBEXECDIR}")
    file(RELATIVE_PATH PROTON_VPN_KDE_INSTALL_LIBEXECDIR
        "${CMAKE_INSTALL_PREFIX}"
        "${CMAKE_INSTALL_LIBEXECDIR}"
    )
else()
    set(PROTON_VPN_KDE_INSTALL_LIBEXECDIR
        "${CMAKE_INSTALL_LIBEXECDIR}")
endif()
configure_file(
    backend/proton-vpn-kde-backend.in
    ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-backend
    @ONLY
)
if(PROTON_VPN_KDE_ENABLE_SUPPORT_REPORT_SUBMISSION)
    set(PROTON_VPN_KDE_PYTHON_SUPPORT_REPORT_SUBMISSION_ENABLED True)
else()
    set(PROTON_VPN_KDE_PYTHON_SUPPORT_REPORT_SUBMISSION_ENABLED False)
endif()
if(PROTON_VPN_KDE_ENABLE_CRASH_REPORT_SUBMISSION)
    set(PROTON_VPN_KDE_PYTHON_CRASH_REPORT_SUBMISSION_ENABLED True)
else()
    set(PROTON_VPN_KDE_PYTHON_CRASH_REPORT_SUBMISSION_ENABLED False)
endif()
configure_file(
    backend/proton_vpn_kde_backend/_build_features.py.in
    ${CMAKE_CURRENT_BINARY_DIR}/_build_features.py
    @ONLY
)

install(TARGETS proton-vpn-kde proton-vpn-kde-agent
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(
    TARGETS proton-vpn-kde-runner
    LIBRARY DESTINATION ${KDE_INSTALL_PLUGINDIR}/kf6/krunner
)
install(
    PROGRAMS ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-backend
    DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(
    DIRECTORY backend/proton_vpn_kde_backend
    DESTINATION ${CMAKE_INSTALL_LIBEXECDIR}/proton-vpn-kde
    FILES_MATCHING PATTERN "*.py"
    PATTERN "__pycache__" EXCLUDE
)
install(
    FILES ${CMAKE_CURRENT_BINARY_DIR}/_build_features.py
    DESTINATION ${CMAKE_INSTALL_LIBEXECDIR}/proton-vpn-kde/proton_vpn_kde_backend
)
install(FILES data/proton-vpn-kde.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)
install(
    FILES
        data/plasma-vpn.svg
        data/plasma-vpn-light.svg
        data/plasma-vpn-dark.svg
    DESTINATION ${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps
)
install(FILES data/proton-vpn-kde.notifyrc DESTINATION ${CMAKE_INSTALL_DATADIR}/knotifications6)
install(
    FILES ${PROTON_VPN_KDE_QM_FILES}
    DESTINATION ${CMAKE_INSTALL_DATADIR}/proton-vpn-kde/translations
)
install(
    FILES ${CMAKE_CURRENT_BINARY_DIR}/quest.entropy.PlasmaVPN.Backend.service
    DESTINATION ${CMAKE_INSTALL_DATADIR}/dbus-1/services
)
install(
    FILES ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-backend.service
    DESTINATION ${KDE_INSTALL_SYSTEMDUSERUNITDIR}
)
install(
    FILES ${CMAKE_CURRENT_BINARY_DIR}/quest.entropy.PlasmaVPN.Agent.service
    DESTINATION ${CMAKE_INSTALL_DATADIR}/dbus-1/services
)
install(
    FILES ${CMAKE_CURRENT_BINARY_DIR}/quest.entropy.PlasmaVPN.ControlCenter.service
    DESTINATION ${CMAKE_INSTALL_DATADIR}/dbus-1/services
)
install(
    FILES ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-agent.service
    DESTINATION ${KDE_INSTALL_SYSTEMDUSERUNITDIR}
)
