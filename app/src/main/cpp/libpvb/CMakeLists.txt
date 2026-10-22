# PVB speaker engine (C++17). Built as its own shared library so the JamesDSP code stays untouched.
add_library(pvbengine SHARED
        ${CMAKE_CURRENT_LIST_DIR}/pvb_engine.cpp
        ${CMAKE_CURRENT_LIST_DIR}/pvb_engine.h
        ${CMAKE_CURRENT_LIST_DIR}/pvb_analysis.cpp
        ${CMAKE_CURRENT_LIST_DIR}/pvb_analysis.h
        ${CMAKE_CURRENT_LIST_DIR}/pvb_dsp.h
        ${CMAKE_CURRENT_LIST_DIR}/pvb_fastmath.h
        ${CMAKE_CURRENT_LIST_DIR}/pvb_simd.h
        ${CMAKE_CURRENT_LIST_DIR}/pvb_vb52.cpp
        ${CMAKE_CURRENT_LIST_DIR}/pvb_vb.cpp
        ${CMAKE_CURRENT_LIST_DIR}/pvb_vb.h
        ${CMAKE_CURRENT_LIST_DIR}/pvb_vb_tables.h
        ${CMAKE_CURRENT_LIST_DIR}/pvb_jni.cpp)

set_target_properties(pvbengine PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
# The project-wide flags use -Ofast; this library needs strict IEEE behaviour (NaN checks,
# repeatable filter maths), so it switches fast-math off again.
target_compile_options(pvbengine PRIVATE -O2 -fno-fast-math -Wall -Wextra)
target_include_directories(pvbengine PRIVATE ${CMAKE_CURRENT_LIST_DIR})
