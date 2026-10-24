# Rootnote root build: librootnotefx.so, the JamesDSP audio effect with the PVB engine (jamesdsp_rootnote.c).
# Standalone (not part of the app's build, so the rootless APK doesn't carry it): tools/rootfx/build_android.sh builds
# it with the NDK for the Magisk module (tools/rootfx/module), tools/rootfx/build_host.sh for the host test.
cmake_minimum_required(VERSION 3.18...3.31)
project(rootnotefx LANGUAGES C CXX)
set(ROOTFX_JDSP ${CMAKE_CURRENT_LIST_DIR}/../libjamesdsp/Main/libjamesdsp/jni/jamesdsp)
file(GLOB_RECURSE ROOTFX_JDSP_SOURCES CONFIGURE_DEPENDS ${ROOTFX_JDSP}/jdsp/*.c)
add_library(rootnotefx SHARED
        ${CMAKE_CURRENT_LIST_DIR}/jamesdsp_rootnote.c
        ${CMAKE_CURRENT_LIST_DIR}/rootfx_pvb.cpp
        ${ROOTFX_JDSP}/cpthread.c
        ${ROOTFX_JDSP_SOURCES}
        ${CMAKE_CURRENT_LIST_DIR}/../EELStdOutExtension.c
        ${CMAKE_CURRENT_LIST_DIR}/../libpvb/pvb_engine.cpp
        ${CMAKE_CURRENT_LIST_DIR}/../libpvb/pvb_analysis.cpp
        ${CMAKE_CURRENT_LIST_DIR}/../libpvb/pvb_vb52.cpp
        ${CMAKE_CURRENT_LIST_DIR}/../libpvb/pvb_vb.cpp)
target_include_directories(rootnotefx PRIVATE ${ROOTFX_JDSP} ${ROOTFX_JDSP}/jdsp ${CMAKE_CURRENT_LIST_DIR}
        ${CMAKE_CURRENT_LIST_DIR}/../libpvb)
# no DEBUG logging inside audioserver (the project-wide flags define it)
target_compile_options(rootnotefx PRIVATE -UDEBUG $<$<COMPILE_LANGUAGE:C>:-std=gnu11 -O2 -w -Wno-error=implicit-function-declaration -Wno-error=incompatible-function-pointer-types -Wno-error=int-conversion>
        $<$<COMPILE_LANGUAGE:CXX>:-std=c++17 -O2 -fno-fast-math -fvisibility-inlines-hidden>)
# audioserver loads it with dlopen: no C++ runtime of its own to rely on, everything hidden but the library symbol
set_target_properties(rootnotefx PROPERTIES C_VISIBILITY_PRESET hidden CXX_VISIBILITY_PRESET hidden)
if(ANDROID)
    target_link_options(rootnotefx PRIVATE -static-libstdc++ -Wl,--gc-sections,--exclude-libs,ALL)
endif()
if(ANDROID)
    target_link_libraries(rootnotefx log m)
else()
    target_link_libraries(rootnotefx m pthread)
endif()
