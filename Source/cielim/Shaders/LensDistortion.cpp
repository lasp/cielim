//=================== Copyright (c) 2026 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FLensDistortion class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "LensDistortion.h"
IMPLEMENT_GLOBAL_SHADER(FLensDistortion, "/CielimShaders/LensDistortion.usf", "MainPS", SF_Pixel);
