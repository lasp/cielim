//=================== Copyright (c) 2025 Laboratory for Atmospheric and Space Physics ===================//
//
// Purpose: Implements the global shader wrapped by the FCompositeAdd class.
//
// License: MIT License. See LICENSE file.
//
//=======================================================================================================//

#include "CompositeAdd.h"
IMPLEMENT_GLOBAL_SHADER(FCompositeAdd, "/CielimShaders/CompositeAdd.usf", "MainPS", SF_Pixel);
