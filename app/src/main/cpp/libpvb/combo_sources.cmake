option(ROOTNOTE_DRY_UNFILTERED "Filter only the harmonic branch (V1)" OFF)
set(ROOTNOTE_ENGINE_SOURCES
    ${CMAKE_CURRENT_LIST_DIR}/pvb_engine.cpp
    ${CMAKE_CURRENT_LIST_DIR}/pvb_analysis.cpp
    ${CMAKE_CURRENT_LIST_DIR}/pvb_vb.cpp
    ${CMAKE_CURRENT_LIST_DIR}/pvb_vb52.cpp
    ${CMAKE_CURRENT_LIST_DIR}/combo1/pvb_vb.cpp
    ${CMAKE_CURRENT_LIST_DIR}/combo1/pvb_vb52.cpp
    ${CMAKE_CURRENT_LIST_DIR}/combo1/way3alt1_synth.cpp)
function(rootnote_combo_options target)
    target_compile_options(${target} PRIVATE $<$<COMPILE_LANGUAGE:CXX>:-ffp-contract=off>)
    if(ROOTNOTE_DRY_UNFILTERED)
        target_compile_definitions(${target} PRIVATE ROOTNOTE_DRY_UNFILTERED=1)
    endif()
endfunction()
