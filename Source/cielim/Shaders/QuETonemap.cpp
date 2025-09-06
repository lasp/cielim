//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FQuETonemap class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "QuETonemap.h"
IMPLEMENT_GLOBAL_SHADER(FQuETonemap, "/CielimShaders/QuETonemap.usf", "MainPS", SF_Pixel);
