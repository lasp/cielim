//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FGaussianPSF class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "GaussianPSF.h"
IMPLEMENT_GLOBAL_SHADER(FGaussianPSF, "/CielimShaders/GaussianPSF.usf", "MainPS", SF_Pixel);
