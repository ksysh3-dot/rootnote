/* Host build only: the Android log function the JamesDSP sources call (prints nothing). */
#include <stdarg.h>
__attribute__((visibility("default"))) int __android_log_print(int prio, const char *tag, const char *fmt, ...) {
    (void)prio; (void)tag; (void)fmt;
    return 0;
}
