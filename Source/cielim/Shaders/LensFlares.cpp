//=================== Copyright (c) 2026 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FLensFlares class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "LensFlares.h"
IMPLEMENT_GLOBAL_SHADER(FLensFlares, "/CielimShaders/LensFlares.usf", "MainPS", SF_Pixel);
