#include <jni.h>
#include <atomic>
#include <cstddef>
#include <new>
static std::atomic<bool> armed{false};static std::atomic<unsigned long long> count{0};
extern "C" void* __real__Znwm(std::size_t);
extern "C" void* __real__Znam(std::size_t);
extern "C" void* __wrap__Znwm(std::size_t n) {if(armed.load())++count;return __real__Znwm(n);}
extern "C" void* __wrap__Znam(std::size_t n) {if(armed.load())++count;return __real__Znam(n);}
extern "C" JNIEXPORT void JNICALL Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_allocationProbe(JNIEnv*,jclass,jboolean on) {if(on)count=0;armed=on!=0;}
extern "C" JNIEXPORT jlong JNICALL Java_me_timschneeberger_rootlessjamesdsp_pvb_PvbNative_allocationCount(JNIEnv*,jclass) {return static_cast<jlong>(count.load());}
