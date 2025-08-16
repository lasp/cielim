//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FGammaCorrect class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "GammaCorrect.h"
IMPLEMENT_GLOBAL_SHADER(FGammaCorrect, "/CielimShaders/GammaCorrect.usf", "MainPS", SF_Pixel);
