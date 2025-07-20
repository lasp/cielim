//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FSignalGain class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "SignalGain.h"
IMPLEMENT_GLOBAL_SHADER(FSignalGain, "/CielimShaders/SignalGain.usf", "MainPS", SF_Pixel);
