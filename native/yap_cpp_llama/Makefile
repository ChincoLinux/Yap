CXX ?= g++
CXXFLAGS ?= -O3 -Wall -fPIC -std=c++17 -pthread

TARGET_LINUX = libyap_cpp_llama.so
TARGET_WIN = yap_cpp_llama.dll

ifeq ($(OS),Windows_NT)
    TARGET = $(TARGET_WIN)
    LDFLAGS = -shared
else
    TARGET = $(TARGET_LINUX)
    LDFLAGS = -shared -Wl,-soname,$(TARGET_LINUX)
endif

all: $(TARGET)

$(TARGET): yap_llama_bridge.cpp yap_llama_bridge.h
	$(CXX) $(CXXFLAGS) $(LDFLAGS) yap_llama_bridge.cpp -o $(TARGET)

clean:
	rm -f $(TARGET_LINUX) $(TARGET_WIN) *.o
