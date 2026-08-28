cmake_minimum_required(VERSION 3.24)

project(proton-vpn-kde VERSION 0.8.1 LANGUAGES CXX)

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
find_package(KF6DBusAddons 6.0 REQUIRED)
find_package(KF6GlobalAccel 6.0 REQUIRED)
find_package(KF6Notifications 6.0 REQUIRED)
find_package(KF6Runner 6.0 REQUIRED)
find_package(KF6Service 6.0 REQUIRED)
find_package(OpenSSL 3.0 REQUIRED COMPONENTS Crypto)

qt_standard_project_setup(REQUIRES 6.8)

qt_add_executable(proton-vpn-kde
    src/AppSettings.cpp
    src/AppSettings.h
    src/CustomDnsModel.cpp
    src/CustomDnsModel.h
    src/InstalledApplicationModel.cpp
    src/InstalledApplicationModel.h
    src/NotificationIntegration.cpp
    src/NotificationIntegration.h
    src/SecretTransport.cpp
    src/SecretTransport.h
    src/ShortcutIntegration.cpp
    src/ShortcutIntegration.h
    src/SplitTunnelingModel.cpp
    src/SplitTunnelingModel.h
    src/main.cpp
    src/LocationModels.cpp
    src/LocationModels.h
    src/TrayIntegration.cpp
    src/TrayIntegration.h
    src/UpdateChannel.cpp
    src/UpdateChannel.h
    src/VpnController.cpp
    src/VpnController.h
    src/VpnSettingsModel.cpp
    src/VpnSettingsModel.h
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
        qml/LocationsPage.qml
        qml/OverviewPage.qml
        qml/ReportIssuePage.qml
        qml/ReleaseNotesPage.qml
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
    KF6::DBusAddons
    KF6::GlobalAccel
    KF6::Notifications
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
)

if(TARGET KF6::StatusNotifierItem)
    target_link_libraries(proton-vpn-kde PRIVATE KF6::StatusNotifierItem)
    target_compile_definitions(proton-vpn-kde PRIVATE HAVE_KSTATUSNOTIFIERITEM=1)
endif()

add_library(proton-vpn-kde-runner MODULE
    runner/ProtonVpnRunner.cpp
    runner/ProtonVpnRunner.h
    runner/RunnerCommand.cpp
    runner/RunnerCommand.h
)
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
    ${CMAKE_CURRENT_BINARY_DIR}
)
target_link_libraries(proton-vpn-kde-runner PRIVATE
    Qt6::Core
    Qt6::DBus
    KF6::CoreAddons
    KF6::Runner
)
target_compile_definitions(proton-vpn-kde-runner PRIVATE
    PROTON_VPN_KDE_EXECUTABLE="${CMAKE_INSTALL_FULL_BINDIR}/proton-vpn-kde"
)
target_compile_options(proton-vpn-kde-runner PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
)

if(BUILD_TESTING)
    find_package(Qt6 6.8 REQUIRED COMPONENTS Test)
    find_program(DBUS_RUN_SESSION_EXECUTABLE dbus-run-session)
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
    add_test(NAME app-settings-tests COMMAND app-settings-tests)

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

    if(DBUS_RUN_SESSION_EXECUTABLE)
        file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data)
        add_test(
            NAME auth-dbus-smoke
            COMMAND ${CMAKE_COMMAND} -E env
                "XDG_DATA_DIRS=${CMAKE_CURRENT_BINARY_DIR}/test-xdg-data"
                ${DBUS_RUN_SESSION_EXECUTABLE} --
                    ${CMAKE_CURRENT_SOURCE_DIR}/scripts/smoke-auth-demo.sh
        )
    endif()
endif()

configure_file(
    data/proton.vpn.app.kde.backend.service.in
    ${CMAKE_CURRENT_BINARY_DIR}/proton.vpn.app.kde.backend.service
    @ONLY
)
configure_file(
    data/proton-vpn-kde-backend.service.in
    ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-backend.service
    @ONLY
)
configure_file(
    backend/proton-vpn-kde-backend.in
    ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-backend
    @ONLY
)

install(TARGETS proton-vpn-kde RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
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
install(FILES data/proton-vpn-kde.desktop DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)
install(FILES data/proton-vpn-kde.svg DESTINATION ${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps)
install(FILES data/proton-vpn-kde.notifyrc DESTINATION ${CMAKE_INSTALL_DATADIR}/knotifications6)
install(
    FILES ${CMAKE_CURRENT_BINARY_DIR}/proton.vpn.app.kde.backend.service
    DESTINATION ${CMAKE_INSTALL_DATADIR}/dbus-1/services
)
install(
    FILES ${CMAKE_CURRENT_BINARY_DIR}/proton-vpn-kde-backend.service
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/systemd/user
)
