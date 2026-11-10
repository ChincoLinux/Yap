cmake_minimum_required(VERSION 3.14)
project(yap_cpp_llama CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(yap_cpp_llama SHARED
    yap_llama_bridge.cpp
)

target_include_directories(yap_cpp_llama PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

if(WIN32)
    set_target_properties(yap_cpp_llama PROPERTIES PREFIX "")
endif()
