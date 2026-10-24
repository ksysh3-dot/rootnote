// Host test only: the engine's parameter count, from the engine's own header.
#include "pvb_engine.h"
extern "C" int harness_param_count() { return pvb::P_COUNT; }
