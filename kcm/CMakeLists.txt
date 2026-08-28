set(_proton_saved_build_shared_libs "${BUILD_SHARED_LIBS}")
set(BUILD_SHARED_LIBS ON)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib")

kcmutils_add_qml_kcm(kcm_proton_vpn_kde
    SOURCES
        ProtonVpnKcm.cpp
        ProtonVpnKcm.h
        ../src/AppSettings.cpp
        ../src/AppSettings.h
        ../src/TranslationLoader.cpp
        ../src/TranslationLoader.h
)

set(BUILD_SHARED_LIBS "${_proton_saved_build_shared_libs}")

set_target_properties(kcm_proton_vpn_kde PROPERTIES PREFIX "")
target_include_directories(kcm_proton_vpn_kde PRIVATE ../src)
target_link_libraries(kcm_proton_vpn_kde PRIVATE
    Qt6::Core
    KF6::ConfigCore
    KF6::CoreAddons
    KF6::KCMUtilsQuick
)
target_compile_definitions(kcm_proton_vpn_kde PRIVATE
    PROTON_VPN_KDE_EXECUTABLE="${CMAKE_INSTALL_FULL_BINDIR}/proton-vpn-kde"
)
proton_vpn_kde_enable_translations(kcm_proton_vpn_kde)
target_compile_options(kcm_proton_vpn_kde PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic>
)

if(BUILD_TESTING)
    add_executable(proton-vpn-kcm-tests
        ../tests/ProtonVpnKcmTest.cpp
    )
    target_link_libraries(proton-vpn-kcm-tests PRIVATE
        Qt6::Core
        Qt6::Gui
        Qt6::Quick
        Qt6::Test
        KF6::CoreAddons
        KF6::KCMUtilsQuick
    )
    target_compile_definitions(proton-vpn-kcm-tests PRIVATE
        PROTON_VPN_KCM_PLUGIN_DIR="$<TARGET_FILE_DIR:kcm_proton_vpn_kde>"
        PROTON_VPN_KCM_PLUGIN_NAME="$<TARGET_FILE_BASE_NAME:kcm_proton_vpn_kde>"
    )
    add_dependencies(proton-vpn-kcm-tests kcm_proton_vpn_kde)
    add_test(NAME proton-vpn-kcm-tests COMMAND proton-vpn-kcm-tests)
    set_tests_properties(proton-vpn-kcm-tests PROPERTIES
        ENVIRONMENT "QT_QPA_PLATFORM=offscreen"
    )
endif()
