# PVB speaker engine, COMBO default.
include(${CMAKE_CURRENT_LIST_DIR}/combo_sources.cmake)
add_library(pvbengine SHARED ${ROOTNOTE_ENGINE_SOURCES} ${CMAKE_CURRENT_LIST_DIR}/pvb_jni.cpp)
set_target_properties(pvbengine PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
target_compile_options(pvbengine PRIVATE -O2 -fno-fast-math -Wall -Wextra)
target_include_directories(pvbengine PRIVATE ${CMAKE_CURRENT_LIST_DIR})
rootnote_combo_options(pvbengine)
