//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FReadNoise class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "ReadNoise.h"
IMPLEMENT_GLOBAL_SHADER(FReadNoise, "/CielimShaders/ReadNoise.usf", "MainPS", SF_Pixel);
