cmake_minimum_required(VERSION 3.24)

project(proton-vpn-kde VERSION 0.4.0 LANGUAGES CXX)

include(GNUInstallDirs)
include(CTest)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 6.8 REQUIRED COMPONENTS
    Core
    DBus
    Gui
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
find_package(ECM 6.0 QUIET NO_MODULE)
if(ECM_FOUND)
    list(APPEND CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
    find_package(KF6StatusNotifierItem QUIET)
endif()
find_package(KF6Config 6.0 REQUIRED)
find_package(KF6Notifications 6.0 REQUIRED)
find_package(OpenSSL 3.0 REQUIRED COMPONENTS Crypto)

qt_standard_project_setup(REQUIRES 6.8)

qt_add_executable(proton-vpn-kde
    src/AppSettings.cpp
    src/AppSettings.h
    src/NotificationIntegration.cpp
    src/NotificationIntegration.h
    src/SecretTransport.cpp
    src/SecretTransport.h
    src/main.cpp
    src/LocationModels.cpp
    src/LocationModels.h
    src/TrayIntegration.cpp
    src/TrayIntegration.h
    src/VpnController.cpp
    src/VpnController.h
)

qt_add_qml_module(proton-vpn-kde
    URI Proton.VPN.KDE
    VERSION 1.0
    NO_IMPORT_SCAN
    QML_FILES
        qml/Main.qml
        qml/AccountPage.qml
        qml/LocationsPage.qml
        qml/OverviewPage.qml
        qml/ServersPage.qml
        qml/SettingsPage.qml
        qml/SignInPage.qml
)

target_link_libraries(proton-vpn-kde PRIVATE
    Qt6::Core
    Qt6::DBus
    Qt6::Gui
    Qt6::Qml
    Qt6::Quick
    Qt6::QuickControls2
    Qt6::Widgets
    KF6::ConfigCore
    KF6::Notifications
    OpenSSL::Crypto
)

target_compile_options(proton-vpn-kde PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
)
target_compile_definitions(proton-vpn-kde PRIVATE _GNU_SOURCE)

if(TARGET KF6::StatusNotifierItem)
    target_link_libraries(proton-vpn-kde PRIVATE KF6::StatusNotifierItem)
    target_compile_definitions(proton-vpn-kde PRIVATE HAVE_KSTATUSNOTIFIERITEM=1)
endif()

if(BUILD_TESTING)
    find_package(Qt6 6.8 REQUIRED COMPONENTS Test)
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

    add_test(
        NAME backend-tests
        COMMAND ${CMAKE_COMMAND} -E env
            "PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}/backend"
            ${Python3_EXECUTABLE} -m unittest discover
            -s ${CMAKE_CURRENT_SOURCE_DIR}/backend/tests -v
    )

    find_program(DBUS_RUN_SESSION_EXECUTABLE dbus-run-session)
    if(DBUS_RUN_SESSION_EXECUTABLE)
        add_test(
            NAME auth-dbus-smoke
            COMMAND ${DBUS_RUN_SESSION_EXECUTABLE} --
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
