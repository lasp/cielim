//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FDistantObjects shader classes.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "DistantObjects.h"

IMPLEMENT_GLOBAL_SHADER(FDistantObjectsVS, "/CielimShaders/DistantObjects.usf", "MainVS", SF_Vertex);
IMPLEMENT_GLOBAL_SHADER(FDistantObjectsPS, "/CielimShaders/DistantObjects.usf", "MainPS", SF_Pixel);
