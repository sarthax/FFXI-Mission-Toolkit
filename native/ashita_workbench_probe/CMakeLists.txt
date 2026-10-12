cmake_minimum_required(VERSION 3.22)
project(workbench_native_probe LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "Ashita v4 native plugin requires Windows.")
endif()
if(NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "Ashita v4 requires an x86 (32-bit) plugin. Configure Visual Studio with -A Win32.")
endif()
if(NOT DEFINED ENV{ASHITA4_SDK_PATH})
    message(FATAL_ERROR "Set ASHITA4_SDK_PATH to Ashita's plugins/sdk folder.")
endif()
file(TO_CMAKE_PATH "$ENV{ASHITA4_SDK_PATH}" ASHITA_SDK)
if(NOT EXISTS "${ASHITA_SDK}/Ashita.h")
    message(FATAL_ERROR "No Ashita.h at ASHITA4_SDK_PATH.")
endif()

add_library(workbench_native_probe MODULE
    workbench_native_probe.cpp
    movement_adapter.h
    passive_packet_queue.h
    native_packet_jsonl.h
    native_packet_writer.h
    exports.def)
target_include_directories(workbench_native_probe PRIVATE "${ASHITA_SDK}")
target_compile_features(workbench_native_probe PRIVATE cxx_std_20)
target_compile_definitions(workbench_native_probe PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
set_target_properties(workbench_native_probe PROPERTIES PREFIX "" OUTPUT_NAME "workbench_native_probe")
