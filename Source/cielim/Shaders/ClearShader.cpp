//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FClearShader class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "ClearShader.h"
IMPLEMENT_GLOBAL_SHADER(FClearShader, "/CielimShaders/ClearShader.usf", "MainPS", SF_Pixel);
