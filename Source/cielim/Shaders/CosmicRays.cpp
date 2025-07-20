//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FCosmicRays class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CosmicRays.h"
IMPLEMENT_GLOBAL_SHADER(FCosmicRays, "/CielimShaders/CosmicRays.usf", "MainPS", SF_Pixel);
